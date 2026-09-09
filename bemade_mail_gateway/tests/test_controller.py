# Copyright (C) 2026 Bemade Inc.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""HTTP-level tests for the mail gateway controller.

These tests use ``HttpCase`` so the routes go through Odoo's WSGI stack
exactly as a real client would hit them. Auth is intentionally
``auth='none'`` on the controller, so we don't authenticate as any user —
the token alone is what unlocks the endpoint.
"""

from odoo.tests import HttpCase, tagged

SAMPLE_RAW = (
    b"From: sender@example.org\r\n"
    b"To: alias@example.org\r\n"
    b"Subject: probe\r\n"
    b"Message-Id: <probe-1@example.org>\r\n"
    b"\r\n"
    b"body\r\n"
)


@tagged("post_install", "-at_install", "bemade_mail_gateway")
class TestMailGatewayController(HttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Token = cls.env["bemade.mail_gateway.token"]
        # Allow plain HTTP under the test runner (Odoo's HttpCase test
        # client speaks HTTP, not HTTPS).
        cls.env["ir.config_parameter"].sudo().set_param("bemade_mail_gateway.allow_http", "True")

        # Ensure an alias domain exists so mail routing works in HttpCase.
        # HttpCase commits setUpClass data, making it visible to HTTP requests.
        catchall = (
            cls.env["ir.config_parameter"].sudo().get_param("mail.catchall.domain") or "example.org"
        )
        alias_domain = cls.env["mail.alias.domain"].sudo().search(
            [("name", "=", catchall)], limit=1
        )
        if not alias_domain:
            alias_domain = cls.env["mail.alias.domain"].sudo().create({"name": catchall})
        cls.alias_domain = alias_domain
        cls.env.company.sudo().alias_domain_id = alias_domain

        # Channel + alias committed in setUpClass → visible to HTTP requests.
        cls.test_channel = cls.env["discuss.channel"].sudo().create(
            {"name": "ctl-test-channel", "channel_type": "channel"}
        )
        chan_model_id = (
            cls.env["ir.model"].sudo().search([("model", "=", "discuss.channel")], limit=1).id
        )
        cls.test_alias = cls.env["mail.alias"].sudo().create(
            {
                "alias_name": "ctl-alias",
                "alias_domain_id": alias_domain.id,
                "alias_model_id": chan_model_id,
                "alias_force_thread_id": cls.test_channel.id,
                "alias_contact": "everyone",
            }
        )

    def _post(self, path, body=b"", headers=None):
        url = self.base_url() + path
        return self.opener.post(
            url, data=body, headers=headers or {}, allow_redirects=False, timeout=10
        )

    def _get(self, path, headers=None):
        url = self.base_url() + path
        return self.opener.get(url, headers=headers or {}, allow_redirects=False, timeout=10)

    # ---- /health ----------------------------------------------------------

    def test_health_returns_200_without_auth(self):
        r = self._get("/bemade/mail-gateway/health")
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["ok"])
        self.assertIn("module_version", body)
        self.assertIn("odoo_version", body)

    # ---- /check -----------------------------------------------------------

    def test_check_without_token_returns_401(self):
        r = self._post("/bemade/mail-gateway/check")
        self.assertEqual(r.status_code, 401)
        self.assertEqual(r.json(), {"ok": False, "error": "unauthorized"})

    def test_check_with_invalid_token_returns_401(self):
        r = self._post(
            "/bemade/mail-gateway/check",
            headers={"X-Bemade-Token": "definitely-not-a-real-token"},
        )
        self.assertEqual(r.status_code, 401)

    def test_check_with_valid_token_returns_200(self):
        _, raw = self.Token.action_generate("ctl-check-1")
        r = self._post("/bemade/mail-gateway/check", headers={"X-Bemade-Token": raw})
        self.assertEqual(r.status_code, 200)
        body = r.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["token_label"], "ctl-check-1")

    def test_check_with_revoked_token_returns_401(self):
        rec, raw = self.Token.action_generate("ctl-check-revoked")
        rec.action_revoke()
        r = self._post("/bemade/mail-gateway/check", headers={"X-Bemade-Token": raw})
        self.assertEqual(r.status_code, 401)

    # ---- /process ---------------------------------------------------------

    def test_process_without_token_returns_401(self):
        r = self._post("/bemade/mail-gateway/process", body=SAMPLE_RAW)
        self.assertEqual(r.status_code, 401)

    def test_process_with_invalid_token_returns_401(self):
        r = self._post(
            "/bemade/mail-gateway/process",
            body=SAMPLE_RAW,
            headers={"X-Bemade-Token": "wrong"},
        )
        self.assertEqual(r.status_code, 401)

    def test_process_with_empty_body_returns_400(self):
        _, raw = self.Token.action_generate("ctl-empty")
        r = self._post(
            "/bemade/mail-gateway/process",
            body=b"",
            headers={"X-Bemade-Token": raw},
        )
        self.assertEqual(r.status_code, 400)
        body = r.json()
        self.assertFalse(body["ok"])
        self.assertEqual(body["error"], "bad_request")

    def test_process_with_no_alias_returns_422(self):
        """No `alias@example.org` exists in this DB → 422 no_route."""
        _, raw = self.Token.action_generate("ctl-no-alias")
        r = self._post(
            "/bemade/mail-gateway/process",
            body=SAMPLE_RAW,
            headers={"X-Bemade-Token": raw},
        )
        self.assertEqual(r.status_code, 422)
        body = r.json()
        self.assertFalse(body["ok"])
        self.assertEqual(body["error"], "no_route")

    def test_process_with_valid_alias_returns_200_and_creates_message(self):
        # Channel, alias and alias_domain are created in setUpClass (committed)
        # so they are visible to the HTTP request's independent cursor.
        catchall = self.alias_domain.name
        msg_id = "<ctl-test@example.org>"
        body_bytes = (
            b"From: sender@example.org\r\n"
            b"To: ctl-alias@" + catchall.encode() + b"\r\n"
            b"Subject: from controller test\r\n"
            b"Message-Id: " + msg_id.encode() + b"\r\n"
            b"\r\n"
            b"hello\r\n"
        )

        _, raw = self.Token.action_generate("ctl-happy-path")
        r = self._post(
            "/bemade/mail-gateway/process",
            body=body_bytes,
            headers={"X-Bemade-Token": raw},
        )
        self.assertEqual(r.status_code, 200, r.text)
        body = r.json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["message_id"], msg_id)

        msgs = (
            self.env["mail.message"]
            .sudo()
            .search(
                [
                    ("model", "=", "discuss.channel"),
                    ("res_id", "=", self.test_channel.id),
                    ("message_id", "=", msg_id),
                ]
            )
        )
        self.assertTrue(msgs, "expected exactly one mail.message for our test")

    def test_process_updates_token_usage(self):
        rec, raw = self.Token.action_generate("ctl-usage")
        self.assertEqual(rec.use_count, 0)
        # Even on no_route (422), token validation succeeded → use_count++
        self._post(
            "/bemade/mail-gateway/process",
            body=SAMPLE_RAW,
            headers={"X-Bemade-Token": raw},
        )
        rec.invalidate_recordset()
        self.assertEqual(rec.use_count, 1)
        self.assertTrue(rec.last_used_at)

    def test_process_save_original_header_is_honoured(self):
        """X-Bemade-Save-Original=1 should propagate to message_process kwargs."""
        from unittest.mock import patch

        _, raw = self.Token.action_generate("ctl-save-orig")
        with patch(
            "odoo.addons.mail.models.mail_thread.MailThread.message_process",
            return_value=False,
        ) as spy:
            self._post(
                "/bemade/mail-gateway/process",
                body=SAMPLE_RAW,
                headers={
                    "X-Bemade-Token": raw,
                    "X-Bemade-Save-Original": "1",
                    "X-Bemade-Strip-Attachments": "0",
                },
            )
        self.assertTrue(spy.called)
        _, kwargs = spy.call_args
        self.assertTrue(kwargs.get("save_original"))
        self.assertFalse(kwargs.get("strip_attachments"))

    def test_process_constant_time_token_check(self):
        """Wrong token responses should not vary noticeably with the
        number of active tokens. Smoke-checked via the same patch the
        model test uses — the call count proves we iterate them all."""
        from unittest.mock import patch

        for i in range(4):
            self.Token.action_generate(f"ctl-ct-{i}")

        with patch(
            "odoo.addons.bemade_mail_gateway.models.bemade_mail_gateway_token.hmac.compare_digest",
            wraps=__import__("hmac").compare_digest,
        ) as spy:
            r = self._post(
                "/bemade/mail-gateway/process",
                body=SAMPLE_RAW,
                headers={"X-Bemade-Token": "wrong-from-controller-test"},
            )
        self.assertEqual(r.status_code, 401)
        self.assertGreaterEqual(spy.call_count, 4)
