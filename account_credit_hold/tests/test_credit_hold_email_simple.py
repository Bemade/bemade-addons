# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date, timedelta
from odoo.tests import common, tagged, Form
from odoo.exceptions import UserError
from odoo import Command, fields
import freezegun
from unittest.mock import patch


@tagged("post_install", "-at_install")
class TestAccountCreditHoldEmailSimple(common.TransactionCase):

    def setUp(self):
        super().setUp()

        # Create test partner
        self.partner = self.env["res.partner"].create(
            {
                "name": "Test Customer",
                "is_company": True,
                "customer_rank": 1,
                "email": "test@example.com",
            }
        )

        # Create followup lines
        self._deactivate_followup_lines()
        self.followup_line_no_hold = self._create_followup_line(
            "First Reminder", 15, False, send_email=True
        )
        self.followup_line_hold = self._create_followup_line(
            "Second Reminder", 30, True, send_email=True
        )

        # Create overdue invoice
        self._create_overdue_invoice()

    def _deactivate_followup_lines(self):
        self.env["account_followup.followup.line"].search([]).unlink()

    def _create_followup_line(
        self, name: str, delay: int, hold: bool, send_email: bool = True
    ):
        vals = {
            "company_id": self.env.company.id,
            "name": name,
            "delay": delay,
            "account_hold": hold,
            "send_email": send_email,
        }
        return self.env["account_followup.followup.line"].create(vals)

    def _create_overdue_invoice(self):
        """Create an overdue invoice for testing"""
        with freezegun.freeze_time("2025-01-01"):
            invoice = self.env["account.move"].create(
                {
                    "partner_id": self.partner.id,
                    "move_type": "out_invoice",
                    "date": "2025-01-01",
                    "invoice_date": "2025-01-01",
                    "invoice_line_ids": [
                        Command.create(
                            {
                                "name": "Test Invoice",
                                "quantity": 1.0,
                                "price_unit": 1000.0,
                            }
                        )
                    ],
                    "invoice_date_due": "2025-01-15",
                }
            )
            invoice.action_post()

    def test_pdf_sent_when_customer_on_hold(self):
        """Test that PDF is sent when customer is on credit hold"""
        # Place partner on credit hold
        self.partner.action_credit_hold()
        self.assertTrue(self.partner.on_hold)

        # Clear any existing attachments
        self.env["ir.attachment"].search(
            [("res_model", "=", "res.partner"), ("res_id", "=", self.partner.id)]
        ).unlink()

        # Send followup email
        options = {
            "partner_id": self.partner.id,
            "followup_line": self.followup_line_hold,
            "send_email": True,
        }

        self.env["account.followup.report"]._send_email(options)

        # Check that PDF attachment was created
        attachments = self.env["ir.attachment"].search(
            [("res_model", "=", "res.partner"), ("res_id", "=", self.partner.id)]
        )
        credit_hold_attachments = attachments.filtered(
            lambda a: "Credit_Hold_Report" in a.name
        )
        self.assertTrue(
            len(credit_hold_attachments) > 0,
            "Credit hold PDF should be created when customer is on hold"
        )

    def test_no_pdf_sent_when_customer_not_on_hold(self):
        """Test that no PDF is sent when customer is NOT on credit hold"""
        # Ensure partner is NOT on credit hold
        self.partner.action_lift_credit_hold()
        self.assertFalse(self.partner.on_hold)

        # Clear any existing attachments
        self.env["ir.attachment"].search(
            [("res_model", "=", "res.partner"), ("res_id", "=", self.partner.id)]
        ).unlink()

        # Send followup email
        options = {
            "partner_id": self.partner.id,
            "followup_line": self.followup_line_hold,
            "send_email": True,
        }

        self.env["account.followup.report"]._send_email(options)

        # Check that NO PDF attachment was created
        attachments = self.env["ir.attachment"].search(
            [("res_model", "=", "res.partner"), ("res_id", "=", self.partner.id)]
        )
        credit_hold_attachments = attachments.filtered(
            lambda a: "Credit_Hold_Report" in a.name
        )
        self.assertEqual(
            len(credit_hold_attachments), 0,
            "No credit hold PDF should be created when customer is not on hold"
        )

    def test_email_body_contains_credit_hold_notice(self):
        """Test that email body contains credit hold notice when customer is on hold"""
        # Place partner on credit hold
        self.partner.action_credit_hold()
        self.assertTrue(self.partner.on_hold)

        # Get email body
        options = {
            "partner_id": self.partner.id,
            "followup_line": self.followup_line_hold,
        }
        body = self.env["account.followup.report"]._get_main_body(options)

        # Check for credit hold notice
        self.assertIn("Credit Hold Notice", body)
        self.assertIn("credit hold due to overdue invoices", body)

    def test_credit_hold_notice_is_not_html_escaped(self):
        """The notice is injected as live HTML, not escaped source text.

        ``super()._get_main_body`` returns ``Markup``. Adding a plain ``str``
        to it goes through ``Markup.__radd__``, which ESCAPES the left operand
        -- so an unwrapped notice reaches the customer as visible ``&lt;div
        style=...&gt;`` markup instead of a styled callout.

        ``on_hold`` is forced through the compute rather than via
        ``action_credit_hold()`` because the ``hold_bg`` stored-compute defect
        described on the skipped tests above clears the hold before the body is
        built; this test deliberately isolates the escaping behaviour from that.
        """
        def _force_on_hold(records):
            for record in records:
                record.on_hold = True

        options = {
            "partner_id": self.partner.id,
            "followup_line": self.followup_line_hold,
        }
        with patch.object(
            type(self.partner), "_compute_on_hold", _force_on_hold
        ):
            body = self.env["account.followup.report"]._get_main_body(options)

        self.assertIn("Credit Hold Notice", body)
        # The notice's own markup must survive as markup ...
        self.assertIn("<strong", body)
        # ... and must not have been escaped into visible source text.
        self.assertNotIn("&lt;div", body)
        self.assertNotIn("&lt;strong", body)

    def test_email_body_no_credit_hold_notice_when_not_on_hold(self):
        """Test that email body does NOT contain credit hold notice when customer is NOT on hold"""
        # Ensure partner is NOT on credit hold
        self.partner.action_lift_credit_hold()
        self.assertFalse(self.partner.on_hold)

        # Get email body
        options = {
            "partner_id": self.partner.id,
            "followup_line": self.followup_line_hold,
        }
        body = self.env["account.followup.report"]._get_main_body(options)

        # Check that credit hold notice is NOT present
        self.assertNotIn("Credit Hold Notice", body)
        self.assertNotIn("credit hold due to overdue invoices", body)

    def test_pdf_generation_works(self):
        """Test that PDF generation works correctly"""
        # Place partner on credit hold
        self.partner.action_credit_hold()
        self.assertTrue(self.partner.on_hold)

        # Generate PDF. Since Odoo 18 the report is identified by ``report_ref``
        # (first positional arg) and the records go to ``res_ids``.
        pdf_content, _dummy = self.env['ir.actions.report']._render_qweb_pdf(
            'account_credit_hold.account_credit_hold_report_action',
            [self.partner.id],
        )

        # Check that PDF is generated (non-empty content)
        self.assertTrue(len(pdf_content) > 0, "PDF should be generated")

    def test_attachment_creation(self):
        """Test that attachment creation works"""
        # Place partner on credit hold
        self.partner.action_credit_hold()

        # Generate attachment
        attachment = self.env["account.followup.report"]._generate_credit_hold_attachment(self.partner)

        # Check that attachment exists
        self.assertIsNotNone(attachment, "Attachment should be created")
        if attachment:  # Add null check for type checker
            self.assertTrue("Credit_Hold_Report" in attachment.name)
            self.assertEqual(attachment.res_model, 'res.partner')
            self.assertEqual(attachment.res_id, self.partner.id)

    def test_pdf_sent_with_different_followup_lines(self):
        """Test that PDF is sent regardless of followup line configuration"""
        # Place partner on credit hold
        self.partner.action_credit_hold()
        self.assertTrue(self.partner.on_hold)

        # Test with both followup lines
        followup_lines = [self.followup_line_no_hold, self.followup_line_hold]

        for followup_line in followup_lines:
            # Clear any existing attachments
            self.env["ir.attachment"].search(
                [("res_model", "=", "res.partner"), ("res_id", "=", self.partner.id)]
            ).unlink()
            # Re-establish the hold each iteration: super()._send_email
            # triggers _compute_followup_status which lifts the hold once
            # the followup has just been sent (correct business logic).
            self.partner.action_credit_hold()

            # Send followup email
            options = {
                "partner_id": self.partner.id,
                "followup_line": followup_line,
                "send_email": True,
            }

            self.env["account.followup.report"]._send_email(options)

            # Check that PDF attachment was created
            attachments = self.env["ir.attachment"].search(
                [("res_model", "=", "res.partner"), ("res_id", "=", self.partner.id)]
            )
            credit_hold_attachments = attachments.filtered(
                lambda a: "Credit_Hold_Report" in a.name
            )
            self.assertTrue(
                len(credit_hold_attachments) > 0,
                f"PDF should be sent for followup line: {followup_line.name}"
            )

    def test_postponed_hold_no_pdf(self):
        """Test that postponed credit hold doesn't send PDF"""
        # Place partner on credit hold with postponement
        self.partner.action_credit_hold()
        tomorrow = date.today() + timedelta(days=1)
        self.partner.postpone_hold_until = tomorrow

        # Partner should not be "on_hold" due to postponement
        self.assertFalse(self.partner.on_hold)

        # Send followup email
        options = {
            "partner_id": self.partner.id,
            "followup_line": self.followup_line_hold,
            "send_email": True,
        }
        self.env["account.followup.report"]._send_email(options)

        # Check that NO PDF is sent
        attachments = self.env["ir.attachment"].search(
            [("res_model", "=", "res.partner"), ("res_id", "=", self.partner.id)]
        )
        credit_hold_attachments = attachments.filtered(
            lambda a: "Credit_Hold_Report" in a.name
        )
        self.assertEqual(
            len(credit_hold_attachments), 0,
            "No PDF should be sent when hold is postponed"
        )

    def test_child_partner_inherits_credit_hold(self):
        """Test that child partners inherit credit hold status"""
        # Create child contact
        child_partner = self.env["res.partner"].create({
            "name": "Child Contact",
            "parent_id": self.partner.id,
            "type": "contact",
            "email": "child@example.com",
        })

        # Place parent on credit hold
        self.partner.action_credit_hold()

        # Child should inherit on_hold status
        self.assertTrue(child_partner.on_hold)

        # Send followup email to child
        options = {
            "partner_id": child_partner.id,
            "followup_line": self.followup_line_hold,
            "send_email": True,
        }
        self.env["account.followup.report"]._send_email(options)

        # Check that PDF was created for child
        attachments = self.env["ir.attachment"].search(
            [("res_model", "=", "res.partner"), ("res_id", "=", child_partner.id)]
        )
        credit_hold_attachments = attachments.filtered(
            lambda a: "Credit_Hold_Report" in a.name
        )
        self.assertTrue(
            len(credit_hold_attachments) > 0,
            "PDF should be sent to child partner when parent is on credit hold"
        )

    def test_credit_hold_field_deprecated(self):
        """Test that attach_credit_hold_report field is deprecated but doesn't break functionality"""
        # Check field exists
        followup_line = self.followup_line_hold
        self.assertTrue(hasattr(followup_line, 'attach_credit_hold_report'))

        # Set the field to False (should not affect PDF sending)
        followup_line.attach_credit_hold_report = False
        self.partner.action_credit_hold()

        # Send email - should still include PDF
        options = {
            "partner_id": self.partner.id,
            "followup_line": followup_line,
            "send_email": True,
        }
        self.env["account.followup.report"]._send_email(options)

        # Verify PDF was created despite field being False
        attachments = self.env["ir.attachment"].search(
            [("res_model", "=", "res.partner"), ("res_id", "=", self.partner.id)]
        )
        credit_hold_attachments = attachments.filtered(
            lambda a: "Credit_Hold_Report" in a.name
        )
        self.assertTrue(
            len(credit_hold_attachments) > 0,
            "PDF should be sent regardless of attach_credit_hold_report field value"
        )
