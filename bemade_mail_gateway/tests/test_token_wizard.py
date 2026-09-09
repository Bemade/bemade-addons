# Copyright (C) 2026 Bemade Inc.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
"""Unit tests for the token creation wizard."""

from odoo.exceptions import UserError, ValidationError
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "bemade_mail_gateway")
class TestTokenCreateWizard(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Wizard = cls.env["bemade.mail_gateway.token.create.wizard"]
        cls.Token = cls.env["bemade.mail_gateway.token"]

    def test_generate_creates_record_and_exposes_raw_token(self):
        wiz = self.Wizard.create({"name": "wiz-test-1"})
        self.assertFalse(wiz.generated_token)
        self.assertFalse(wiz.generated_token_id)

        action = wiz.action_generate()

        # Returns an act_window action that re-opens the same wizard record
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], wiz._name)
        self.assertEqual(action["res_id"], wiz.id)
        self.assertEqual(action["target"], "new")

        # The wizard record now carries the raw token + a reference to the
        # persisted token row
        self.assertTrue(wiz.generated_token)
        self.assertGreaterEqual(len(wiz.generated_token), 40)
        self.assertTrue(wiz.generated_token_id)
        self.assertEqual(wiz.generated_token_id.name, "wiz-test-1")

        # The persisted record stores the hash, NOT the raw token
        self.assertNotEqual(
            wiz.generated_token_id.token_hash,
            wiz.generated_token,
            "the stored hash must differ from the raw token",
        )

    def test_generate_twice_on_same_wizard_raises(self):
        wiz = self.Wizard.create({"name": "wiz-test-2"})
        wiz.action_generate()
        with self.assertRaises(UserError):
            wiz.action_generate()

    def test_generate_with_empty_name_propagates_validation_error(self):
        wiz = self.Wizard.create({"name": "   "})
        with self.assertRaises(ValidationError):
            wiz.action_generate()

    def test_generate_with_expiry_persists_to_record(self):
        from datetime import timedelta

        from odoo import fields

        future = fields.Datetime.now() + timedelta(days=7)
        wiz = self.Wizard.create({"name": "wiz-expiry", "expires_at": future})
        wiz.action_generate()
        self.assertEqual(wiz.generated_token_id.expires_at, future)

    def test_action_close_returns_close_action(self):
        wiz = self.Wizard.create({"name": "wiz-close"})
        action = wiz.action_close()
        self.assertEqual(action, {"type": "ir.actions.act_window_close"})

    def test_action_open_create_wizard_returns_act_window(self):
        action = self.Wizard.action_open_create_wizard()
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], self.Wizard._name)
        self.assertEqual(action["target"], "new")
