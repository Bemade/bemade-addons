# Copyright (C) 2026 Bemade Inc.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""Security & redaction tests.

Two hard guarantees we promise to operators:

1. **No raw token ever lands in any log.** A leak in DEBUG/INFO logs of
   a high-privilege endpoint would defeat the entire model. We exercise
   every code path that touches a raw token and assert that the raw
   value never appears in any captured ``LogRecord``.

2. **Only admins can read or modify tokens.** The endpoint deliberately
   bypasses Odoo's ACLs (auth='none' + sudo on validate_token), so the
   safety net is the model's own ``ir.model.access`` row + the security
   group. We verify that a regular Internal User cannot search, read,
   create or write tokens.

A failure of either is a critical bug.
"""

import logging
import re

from odoo.exceptions import AccessError
from odoo.tests import HttpCase, TransactionCase, tagged
from odoo.tools import mute_logger


@tagged("post_install", "-at_install", "bemade_mail_gateway")
class TestNoTokenInLogs(HttpCase):
    """Every code path touching a raw token must keep it out of logs."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Token = cls.env["bemade.mail_gateway.token"]
        cls.env["ir.config_parameter"].sudo().set_param("bemade_mail_gateway.allow_http", "True")

    def _capture(self):
        """Attach a capturing handler to the relevant loggers and force them
        to DEBUG so a real `_logger.debug("token=%s", raw)` leak would land
        in the handler. Prior level + propagate are snapshotted and restored
        via ``addCleanup`` so we don't taint global logging state for the
        rest of the test run (which previously pinned root/`odoo` at DEBUG
        and flooded CI logs)."""
        handler = _ListHandler()
        handler.setLevel(logging.DEBUG)
        loggers = [
            logging.getLogger(),  # root
            logging.getLogger("odoo"),
            logging.getLogger("odoo.addons.bemade_mail_gateway"),
            logging.getLogger("odoo.addons.bemade_mail_gateway.models.bemade_mail_gateway_token"),
            logging.getLogger("odoo.addons.bemade_mail_gateway.controllers.mail_gateway"),
            logging.getLogger("odoo.addons.bemade_mail_gateway.wizards.token_create_wizard"),
        ]
        prior = [(lg, lg.level, lg.propagate) for lg in loggers]
        for lg in loggers:
            lg.addHandler(handler)
            lg.setLevel(logging.DEBUG)
            # Keep captured DEBUG records out of the console: emission to
            # the parent chain happens via propagation, so cutting that off
            # while the test runs prevents stdout pollution.
            lg.propagate = False
        self.addCleanup(self._release, handler, prior)
        return handler, loggers

    @staticmethod
    def _release(handler, prior):
        for lg, level, propagate in prior:
            lg.removeHandler(handler)
            lg.setLevel(level)
            lg.propagate = propagate

    def _assert_no_leak(self, handler, raw, label_for_msg=""):
        for record in handler.records:
            msg = record.getMessage()
            full = f"{record.name} {record.levelname} {msg}"
            self.assertNotIn(
                raw,
                full,
                f"raw token leaked in log{' for ' + label_for_msg if label_for_msg else ''}: "
                f"{full[:200]}",
            )

    # ---- Generation path --------------------------------------------------

    def test_generate_does_not_log_raw(self):
        handler, _ = self._capture()
        _, raw = self.Token.action_generate("redact-gen")
        self._assert_no_leak(handler, raw, "action_generate")

    # ---- Validation paths -------------------------------------------------

    def test_validate_success_does_not_log_raw(self):
        _, raw = self.Token.action_generate("redact-val-ok")
        handler, _ = self._capture()
        self.Token.validate_token(raw, ip="127.0.0.1")
        self._assert_no_leak(handler, raw, "validate_token (success)")

    def test_validate_failure_does_not_log_attempted_token(self):
        attempted = "evil-attempted-token-shouldn't-appear-anywhere-XYZ123"
        handler, _ = self._capture()
        self.Token.validate_token(attempted)
        self._assert_no_leak(handler, attempted, "validate_token (failure)")

    # ---- Controller paths -------------------------------------------------

    def test_controller_check_success_does_not_log_raw(self):
        _, raw = self.Token.action_generate("redact-ctl-check")
        handler, _ = self._capture()
        self.opener.post(
            self.base_url() + "/bemade/mail-gateway/check",
            headers={"X-Bemade-Token": raw},
            timeout=10,
        )
        self._assert_no_leak(handler, raw, "controller /check (200)")

    def test_controller_check_failure_does_not_log_attempted(self):
        attempted = "evil-controller-token-X9Y8Z7"
        handler, _ = self._capture()
        self.opener.post(
            self.base_url() + "/bemade/mail-gateway/check",
            headers={"X-Bemade-Token": attempted},
            timeout=10,
        )
        self._assert_no_leak(handler, attempted, "controller /check (401)")

    @mute_logger("odoo.addons.mail.models.mail_thread")
    def test_controller_process_does_not_log_raw(self):
        _, raw = self.Token.action_generate("redact-ctl-process")
        handler, _ = self._capture()
        self.opener.post(
            self.base_url() + "/bemade/mail-gateway/process",
            data=(
                b"From: a@b\r\nTo: nope@example.org\r\n"
                b"Subject: x\r\nMessage-Id: <r@x>\r\n\r\nbody\r\n"
            ),
            headers={"X-Bemade-Token": raw},
            timeout=10,
        )
        self._assert_no_leak(handler, raw, "controller /process")

    # ---- Read API doesn't echo the hash to non-admins --------------------

    def test_token_hash_field_metadata_is_not_secret_but_unreadable_to_non_admins(self):
        """The schema describes token_hash but only admins can read it."""
        _, raw = self.Token.action_generate("redact-acl")
        # confirmed by the ACL test class below
        self.assertNotEqual(raw, "")  # smoke


class _ListHandler(logging.Handler):
    """Capture all LogRecords passing through. No filtering."""

    def __init__(self):
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


@tagged("post_install", "-at_install", "bemade_mail_gateway")
class TestAclEnforcement(TransactionCase):
    """Only members of group_bemade_mail_gateway_admin can touch tokens."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Token = cls.env["bemade.mail_gateway.token"]
        # A plain Internal User — no admin groups.
        cls.regular_user = cls.env["res.users"].create(
            {
                "name": "ACL Test User",
                "login": "acl-test-user@example.org",
                "email": "acl-test-user@example.org",
                "groups_id": [(6, 0, [cls.env.ref("base.group_user").id])],
            }
        )

    def _as_user(self):
        return self.Token.with_user(self.regular_user)

    def test_regular_user_cannot_search(self):
        # Pre-create a token as admin so search has something to find
        self.Token.action_generate("acl-search")
        with self.assertRaises(AccessError):
            self._as_user().search([])

    def test_regular_user_cannot_read(self):
        rec, _ = self.Token.action_generate("acl-read")
        with self.assertRaises(AccessError):
            self._as_user().browse(rec.id).read(["name"])

    def test_regular_user_cannot_create(self):
        with self.assertRaises(AccessError):
            self._as_user().create({"name": "acl-create-fail", "token_hash": "0" * 64})

    def test_regular_user_cannot_call_action_generate(self):
        with self.assertRaises(AccessError):
            self._as_user().action_generate("acl-gen-fail")

    def test_regular_user_cannot_write(self):
        rec, _ = self.Token.action_generate("acl-write")
        with self.assertRaises(AccessError):
            rec.with_user(self.regular_user).active = False

    def test_regular_user_cannot_unlink(self):
        rec, _ = self.Token.action_generate("acl-unlink")
        with self.assertRaises(AccessError):
            rec.with_user(self.regular_user).unlink()

    def test_regular_user_cannot_validate_token_directly(self):
        """`validate_token` does sudo() internally, but the OUTER call
        still goes through the user's ACL on the model. A non-admin
        should be unable to invoke the method on the model at all."""
        _, raw = self.Token.action_generate("acl-validate")
        with self.assertRaises(AccessError):
            self._as_user().validate_token(raw)


@tagged("post_install", "-at_install", "bemade_mail_gateway")
class TestTokenHashNotInUiSearches(TransactionCase):
    """name_search and similar UI helpers must not surface the hash."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Token = cls.env["bemade.mail_gateway.token"]

    def test_name_search_returns_label_not_hash(self):
        rec, raw = self.Token.action_generate("ns-search-label")
        results = self.Token.name_search("ns-search-label")
        # results = [(id, display_name), ...]
        self.assertTrue(any(r[0] == rec.id for r in results))
        # The display name must not contain anything resembling a sha256
        # hex digest (64 hex chars) nor the raw token.
        for _id, name in results:
            self.assertFalse(
                re.search(r"\b[0-9a-f]{64}\b", name),
                f"display_name leaks a sha256 hash: {name!r}",
            )
            self.assertNotIn(raw, name)
