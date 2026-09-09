# -*- coding: utf-8 -*-
"""Regression tests for bugs found through a client project's CI.

Each test targets a specific bug fixed in 18.0.1.1.3 / 18.0.1.1.4:

  1. ``_render_qweb_pdf`` signature mismatch (must be called on
     ``ir.actions.report`` with a ``report_ref`` argument).
  2. ``_get_main_body`` must capture ``partner.on_hold`` *before*
     calling ``super()``, since the super reads ``followup_line_id``
     which triggers ``_compute_followup_status``, which may itself
     lift the hold.
  3. ``_send_email`` must push raw attachment IDs (not ``(4, id)``
     ORM commands) into ``options['attachment_ids']`` because
     ``account_followup`` forwards that dict straight to
     ``message_post``, which in Odoo 18 rejects ORM commands there.
"""

from datetime import timedelta
from unittest.mock import patch

from odoo import Command, fields
from odoo.tests import common, tagged


@tagged("post_install", "-at_install")
class TestFollowupReportRegression(common.TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.report = cls.env["account.followup.report"]

        cls.partner = cls.env["res.partner"].create({
            "name": "Regression Customer",
            "is_company": True,
            "customer_rank": 1,
            "email": "regression@example.com",
        })

        cls.env["account_followup.followup.line"].search([]).unlink()
        cls.followup_hold = cls.env["account_followup.followup.line"].create({
            "company_id": cls.env.company.id,
            "name": "Hold Reminder",
            "delay": 30,
            "account_hold": True,
            "send_email": True,
        })
        cls.followup_no_hold = cls.env["account_followup.followup.line"].create({
            "company_id": cls.env.company.id,
            "name": "Soft Reminder",
            "delay": 15,
            "account_hold": False,
            "send_email": True,
        })

    def _create_overdue_invoice(self, partner, amount=1000.0, days_overdue=30):
        due_date = fields.Date.today() - timedelta(days=days_overdue)
        invoice = self.env["account.move"].create({
            "partner_id": partner.id,
            "move_type": "out_invoice",
            "invoice_date": due_date,
            "invoice_date_due": due_date,
            "invoice_line_ids": [Command.create({
                "name": "Service",
                "quantity": 1.0,
                "price_unit": amount,
            })],
        })
        invoice.action_post()
        return invoice

    # ------------------------------------------------------------------
    # Bug 1: _render_qweb_pdf signature
    # ------------------------------------------------------------------

    def test_generate_credit_hold_attachment_uses_correct_render_signature(self):
        """``_generate_credit_hold_attachment`` must use the Odoo 18
        signature ``ir.actions.report._render_qweb_pdf(report_ref, ids)``.

        Previously the code called ``report._render_qweb_pdf([ids])`` on
        the report record itself. A consuming module that overrides
        ``_render_qweb_pdf`` on ``ir.actions.report`` forwards ``report_ref``
        straight to ``_get_report``, which then crashes on a list -- which is
        how this surfaced. Stock Odoo fails on the same call for the same
        reason, via the ormcache key on ``_xmlid_lookup``.

        We don't assert the payload is a real PDF — the CI image has no
        wkhtmltopdf, so ``_render_qweb_pdf`` returns rendered HTML in
        that env. The point of this test is that the call doesn't raise.
        """
        self.partner.action_credit_hold()
        attachment = self.report._generate_credit_hold_attachment(self.partner)
        self.assertIsNotNone(attachment)
        self.assertTrue(attachment.datas)

    # ------------------------------------------------------------------
    # Bug 2: _get_main_body must capture on_hold before super()
    # ------------------------------------------------------------------

    def test_get_main_body_keeps_notice_and_no_longer_loses_the_hold(self):
        """The notice survives ``super()``, and so does the hold itself.

        Historically ``super()._get_main_body`` read ``followup_line_id``,
        which triggered ``_compute_followup_status``, which released the hold
        mid-call -- so the notice vanished from the email. The
        ``was_on_hold`` capture in the override fixed the notice; making
        ``hold_bg`` explicit state fixed the underlying release, so building
        an email no longer touches hold state at all.

        Both are asserted: the capture stays as a cheap guard, but the hold
        surviving is the property that actually matters.
        """
        self.partner.action_credit_hold()
        self.assertTrue(self.partner.on_hold)

        body = self.report._get_main_body({
            "partner_id": self.partner.id,
            "followup_line": self.followup_hold,
        })

        self.assertIn("Credit Hold Notice", body)
        self.assertTrue(
            self.partner.on_hold,
            "Rendering a follow-up email must not release the credit hold.",
        )

    def test_get_main_body_no_notice_when_partner_never_on_hold(self):
        """Sanity counterpart: when the partner was never on hold, no
        notice is added even if super() doesn't change anything."""
        self.partner.action_lift_credit_hold()
        self.assertFalse(self.partner.on_hold)

        body = self.report._get_main_body({
            "partner_id": self.partner.id,
            "followup_line": self.followup_no_hold,
        })
        self.assertNotIn("Credit Hold Notice", body)

    # ------------------------------------------------------------------
    # Bug 3: attachment_ids must be a flat list of IDs
    # ------------------------------------------------------------------

    def test_send_email_pushes_flat_attachment_ids(self):
        """``_send_email`` must push raw IDs into
        ``options['attachment_ids']``. In Odoo 18 ``message_post``
        explicitly rejects ``(4, id)`` ORM commands here with::

            ValueError: Posting a message should receive attachments
            records as a list of IDs

        We patch the parent ``_send_email`` to inspect what our
        override hands up the chain, so the test pins the contract
        regardless of whether the upstream call later succeeds or not.
        """
        self.partner.action_credit_hold()
        self.assertTrue(self.partner.on_hold)

        captured = {}

        def fake_super_send_email(self_inner, options):
            captured["attachment_ids"] = list(options.get("attachment_ids") or [])
            return True

        # Patch the parent class (account_followup) directly so we
        # intercept after our override has populated attachment_ids.
        from odoo.addons.account_followup.models.account_followup_report import (
            AccountFollowupReport,
        )
        with patch.object(
            AccountFollowupReport, "_send_email", fake_super_send_email
        ):
            self.report._send_email({
                "partner_id": self.partner.id,
                "followup_line": self.followup_hold,
                "send_email": True,
            })

        self.assertIn("attachment_ids", captured)
        self.assertTrue(captured["attachment_ids"],
                        "An attachment ID should have been added for an on-hold partner")
        for item in captured["attachment_ids"]:
            self.assertIsInstance(
                item, int,
                f"attachment_ids must contain raw IDs, got {item!r} "
                f"(probably a (4, id) ORM command — that raises ValueError "
                f"in message_post in Odoo 18)",
            )

    def test_send_email_preserves_existing_attachment_ids(self):
        """If the caller already pre-populated ``attachment_ids`` with
        raw IDs, our override must append to that list rather than
        replacing it or wrapping the new entry in a tuple."""
        self.partner.action_credit_hold()
        existing_attachment = self.env["ir.attachment"].create({
            "name": "pre-existing.txt",
            "type": "binary",
            "datas": b"aGVsbG8=",  # 'hello' base64
            "res_model": "res.partner",
            "res_id": self.partner.id,
        })

        captured = {}

        def fake_super_send_email(self_inner, options):
            captured["attachment_ids"] = list(options.get("attachment_ids") or [])
            return True

        from odoo.addons.account_followup.models.account_followup_report import (
            AccountFollowupReport,
        )
        with patch.object(
            AccountFollowupReport, "_send_email", fake_super_send_email
        ):
            self.report._send_email({
                "partner_id": self.partner.id,
                "followup_line": self.followup_hold,
                "send_email": True,
                "attachment_ids": [existing_attachment.id],
            })

        self.assertIn(existing_attachment.id, captured["attachment_ids"])
        self.assertGreaterEqual(len(captured["attachment_ids"]), 2,
                                "Override should append, not replace")
        for item in captured["attachment_ids"]:
            self.assertIsInstance(item, int)
