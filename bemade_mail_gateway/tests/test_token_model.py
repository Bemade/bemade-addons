# Copyright (C) 2026 Bemade Inc.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""Unit tests for ``bemade.mail_gateway.token``.

Run via Odoo's test runner:

    odoo-bin -d <db> -i bemade_mail_gateway --test-enable --stop-after-init \\
        --log-level=test --test-tags=bemade_mail_gateway
"""

import hashlib
from datetime import timedelta

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "bemade_mail_gateway")
class TestBemadeMailGatewayToken(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Token = cls.env["bemade.mail_gateway.token"]

    # ---- Generation -------------------------------------------------------

    def test_generate_returns_record_and_raw_token(self):
        rec, raw = self.Token.action_generate("test-1")
        self.assertTrue(rec.id)
        self.assertEqual(rec.name, "test-1")
        self.assertTrue(raw)
        self.assertGreaterEqual(len(raw), 40, "expected ~43 chars from token_urlsafe(32)")

    def test_generated_token_is_hashed_in_db(self):
        rec, raw = self.Token.action_generate("test-2")
        expected = hashlib.sha256(raw.encode("ascii")).hexdigest()
        self.assertEqual(rec.token_hash, expected)
        # The raw token must NOT appear anywhere in the persisted record
        for fname, value in rec.read()[0].items():
            if isinstance(value, str):
                self.assertNotIn(raw, value, f"raw token leaked in field {fname!r}")

    def test_two_generates_yield_different_tokens(self):
        _, raw1 = self.Token.action_generate("test-a")
        _, raw2 = self.Token.action_generate("test-b")
        self.assertNotEqual(raw1, raw2)

    def test_empty_name_rejected(self):
        with self.assertRaises(ValidationError):
            self.Token.action_generate("")
        with self.assertRaises(ValidationError):
            self.Token.action_generate("   ")

    def test_duplicate_name_rejected(self):
        from psycopg2 import IntegrityError

        self.Token.action_generate("dup")
        # SQL `unique(name)` constraint fires inside the savepoint.
        with self.assertRaises(IntegrityError), self.cr.savepoint():
            self.Token.action_generate("dup")

    def test_name_is_trimmed(self):
        rec, _ = self.Token.action_generate("  trim-me  ")
        self.assertEqual(rec.name, "trim-me")

    # ---- Validation: happy path -------------------------------------------

    def test_validate_with_correct_token_returns_record(self):
        rec, raw = self.Token.action_generate("ok")
        result = self.Token.validate_token(raw, ip="10.0.0.1")
        self.assertEqual(result.id, rec.id)

    def test_validate_updates_last_used_fields(self):
        rec, raw = self.Token.action_generate("usage-tracking")
        self.assertFalse(rec.last_used_at)
        self.assertFalse(rec.last_used_ip)
        self.assertEqual(rec.use_count, 0)

        before = fields.Datetime.now()
        self.Token.validate_token(raw, ip="192.168.1.42")
        rec.invalidate_recordset()

        self.assertTrue(rec.last_used_at)
        self.assertGreaterEqual(rec.last_used_at, before)
        self.assertEqual(rec.last_used_ip, "192.168.1.42")
        self.assertEqual(rec.use_count, 1)

        # Second call increments
        self.Token.validate_token(raw, ip="192.168.1.42")
        rec.invalidate_recordset()
        self.assertEqual(rec.use_count, 2)

    def test_validate_truncates_long_ip(self):
        """We don't crash if a stretched IPv6+zone string is passed."""
        rec, raw = self.Token.action_generate("ip-trunc")
        long_ip = "fe80::aaaa:bbbb:cccc:dddd%very-long-zone-identifier-name-here"
        self.Token.validate_token(raw, ip=long_ip)
        rec.invalidate_recordset()
        self.assertLessEqual(len(rec.last_used_ip), 45)

    # ---- Validation: failure modes ----------------------------------------

    def test_validate_with_empty_token_returns_empty(self):
        result = self.Token.validate_token("")
        self.assertFalse(result)

    def test_validate_with_none_token_returns_empty(self):
        # Python typing says str, but defensive against accidental None
        result = self.Token.validate_token(None)  # type: ignore[arg-type]
        self.assertFalse(result)

    def test_validate_with_wrong_token_returns_empty(self):
        self.Token.action_generate("real")
        result = self.Token.validate_token("totally-wrong-token-value")
        self.assertFalse(result)

    def test_validate_with_revoked_token_returns_empty(self):
        rec, raw = self.Token.action_generate("revoke-me")
        rec.action_revoke()
        self.assertFalse(rec.active)
        result = self.Token.validate_token(raw)
        self.assertFalse(result)

    def test_validate_with_expired_token_returns_empty(self):
        past = fields.Datetime.now() - timedelta(hours=1)
        rec, raw = self.Token.action_generate("expired", expires_at=past)
        result = self.Token.validate_token(raw)
        self.assertFalse(result)
        # And it does NOT update last_used (we returned before the write)
        rec.invalidate_recordset()
        self.assertFalse(rec.last_used_at)
        self.assertEqual(rec.use_count, 0)

    def test_validate_with_future_expiry_works(self):
        future = fields.Datetime.now() + timedelta(hours=1)
        rec, raw = self.Token.action_generate("future", expires_at=future)
        result = self.Token.validate_token(raw)
        self.assertEqual(result.id, rec.id)

    # ---- Constant-time guarantee (structural) -----------------------------

    def test_validate_iterates_all_active_tokens(self):
        """Wrong tokens must scan the full active set (no early exit).

        We assert this structurally: with N active tokens and a wrong
        input, every record's ``token_hash`` must be touched. We use a
        spy that counts ``hmac.compare_digest`` invocations.
        """
        from unittest.mock import patch

        for i in range(5):
            self.Token.action_generate(f"ct-{i}")

        with patch(
            "odoo.addons.bemade_mail_gateway.models.bemade_mail_gateway_token.hmac.compare_digest",
            wraps=__import__("hmac").compare_digest,
        ) as spy:
            self.Token.validate_token("wrong-token")
        # At least 5 active tokens existed → at least 5 comparisons.
        # (Other test setups may have created additional records, so use >=.)
        self.assertGreaterEqual(spy.call_count, 5)

    # ---- Revocation -------------------------------------------------------

    def test_action_revoke_sets_inactive(self):
        rec, _ = self.Token.action_generate("revoke")
        self.assertTrue(rec.active)
        rec.action_revoke()
        self.assertFalse(rec.active)

    def test_action_revoke_works_on_recordset(self):
        rec1, _ = self.Token.action_generate("multi-1")
        rec2, _ = self.Token.action_generate("multi-2")
        (rec1 | rec2).action_revoke()
        self.assertFalse(rec1.active)
        self.assertFalse(rec2.active)
