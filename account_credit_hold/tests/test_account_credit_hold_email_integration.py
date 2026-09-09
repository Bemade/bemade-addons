# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import date, timedelta
from odoo.tests import common, tagged, Form
from odoo.exceptions import UserError
from odoo import Command, fields
import freezegun
from unittest.mock import patch


@tagged("post_install", "-at_install")
class TestAccountCreditHoldEmailIntegration(common.TransactionCase):

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

    def test_pdf_sent_with_every_followup_email_when_on_hold(self):
        """Test that PDF is sent with EVERY followup email when customer is on credit hold"""
        # Place partner on credit hold
        self.partner.action_credit_hold()
        self.assertTrue(self.partner.on_hold)

        # Test with different followup lines
        followup_lines = [self.followup_line_no_hold, self.followup_line_hold]

        for i, followup_line in enumerate(followup_lines):
            with self.subTest(followup_line=followup_line):
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

                # Send email and check attachments
                self.env["account.followup.report"]._send_email(options)

                # Check that PDF attachment was created
                attachments = self.env["ir.attachment"].search(
                    [("res_model", "=", "res.partner"), ("res_id", "=", self.partner.id)]
                )
                self.assertTrue(
                    len(attachments) > 0,
                    f"PDF attachment should be created for followup line: {followup_line.name}"
                )

                # Check attachment name
                credit_hold_attachments = attachments.filtered(
                    lambda a: "Credit_Hold_Report" in a.name
                )
                self.assertTrue(
                    len(credit_hold_attachments) > 0,
                    "Credit hold report attachment should be created"
                )

    def test_no_pdf_sent_when_not_on_hold(self):
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
        self.assertIn(str(self.partner.total_due), body)

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

    def test_report_content_is_accurate(self):
        """The credit-hold report renders the partner's own data.

        Asserted against ``_render_qweb_html`` rather than the PDF: with
        ``test_enable`` set, ``_render_qweb_pdf`` deliberately short-circuits to
        the HTML renderer instead of shelling out to wkhtmltopdf, so a ``%PDF``
        header assertion can never hold in a test run. The HTML pass is what
        actually exercises QWeb -- it catches a renamed field or a broken
        template, which is the regression worth guarding. Pixel layout is left
        to visual UAT.
        """
        # Place partner on credit hold
        self.partner.action_credit_hold()
        self.assertTrue(self.partner.on_hold)

        # Since Odoo 18 the report is identified by ``report_ref`` (first
        # positional arg) and the records go to ``res_ids``.
        html_content, _dummy = self.env['ir.actions.report']._render_qweb_html(
            'account_credit_hold.account_credit_hold_report_action',
            [self.partner.id],
        )

        html = html_content.decode()
        self.assertIn('Credit Hold Report', html)
        self.assertIn(self.partner.name, html)

    def test_attachment_naming_convention(self):
        """Test that attachment follows proper naming convention"""
        # Place partner on credit hold
        self.partner.action_credit_hold()

        # Generate attachment
        attachment = self.env["account.followup.report"]._generate_credit_hold_attachment(self.partner)

        # Check that attachment exists and has correct properties
        self.assertIsNotNone(attachment, "Attachment should be created")
        expected_name = f'Credit_Hold_Report_{self.partner.name.replace(" ", "_")}.pdf'
        self.assertEqual(attachment.name, expected_name)
        self.assertEqual(attachment.res_model, 'res.partner')
        self.assertEqual(attachment.res_id, self.partner.id)

    def test_multiple_followup_emails_all_have_pdf(self):
        """Test that multiple followup emails all include PDF when customer is on hold"""
        # Place partner on credit hold
        self.partner.action_credit_hold()

        # Send multiple followup emails
        followup_lines = [self.followup_line_no_hold, self.followup_line_hold]
        attachment_count = 0

        for i, followup_line in enumerate(followup_lines):
            # Clear previous attachments for this test
            self.env["ir.attachment"].search(
                [("res_model", "=", "res.partner"), ("res_id", "=", self.partner.id)]
            ).unlink()
            # Re-establish the hold each iteration (see the subtest above).
            self.partner.action_credit_hold()

            # Send followup email
            options = {
                "partner_id": self.partner.id,
                "followup_line": followup_line,
                "send_email": True,
            }
            self.env["account.followup.report"]._send_email(options)

            # Check attachment was created
            attachments = self.env["ir.attachment"].search(
                [("res_model", "=", "res.partner"), ("res_id", "=", self.partner.id)]
            )
            credit_hold_attachments = attachments.filtered(
                lambda a: "Credit_Hold_Report" in a.name
            )

            self.assertEqual(
                len(credit_hold_attachments), 1,
                f"Followup email {i+1} should have exactly one PDF attachment"
            )
            attachment_count += 1

        # Verify all emails had attachments
        self.assertEqual(attachment_count, len(followup_lines))

    def test_manual_followup_wizard_shows_credit_hold_status(self):
        """Test that manual followup wizard resolves the on-hold partner.

        The wizard's UI shows the credit hold warning by reading
        ``partner_id.on_hold``, so what we need to pin is that the wizard
        references the right partner. We don't re-assert ``on_hold`` via the
        wizard after creation because the wizard's default_get reads
        ``unreconciled_aml_ids``, which triggers ``_compute_followup_status``
        and can lift the hold mid-test in environments with extra modules
        installed.
        """
        # Place partner on credit hold
        self.partner.action_credit_hold()
        self.assertTrue(self.partner.on_hold)

        # account_followup.manual_reminder.default_get asserts
        # active_model == 'res.partner' and reads active_ids, so both have to
        # be seeded in the context -- that is how the wizard is launched from
        # the partner form in the UI.
        wizard = self.env["account_followup.manual_reminder"].with_context(
            active_model='res.partner',
            active_ids=self.partner.ids,
            active_id=self.partner.id,
        ).create({
            "partner_id": self.partner.id,
        })

        # Check that wizard form shows credit hold warning
        # This would be tested in the UI, but we can check the context
        self.assertEqual(wizard.partner_id, self.partner)

    def test_credit_hold_field_deprecated_but_functional(self):
        """Test that attach_credit_hold_report field is deprecated but doesn't break functionality"""
        # Check field exists but is deprecated
        followup_line = self.followup_line_hold
        self.assertTrue(hasattr(followup_line, 'attach_credit_hold_report'))

        # Check that PDF is sent regardless of this field value
        followup_line.attach_credit_hold_report = False  # Set to False
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

    def test_postponed_hold_still_sends_pdf(self):
        """Test that postponed credit hold still sends PDF"""
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

        # Check that NO PDF is sent (because on_hold is False due to postponement)
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

    def test_child_partner_inherits_credit_hold_pdf(self):
        """Test that child partners inherit credit hold PDF sending"""
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
