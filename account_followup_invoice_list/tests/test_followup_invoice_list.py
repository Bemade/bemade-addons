# Acceptance criteria:
# 1. Follow-up email body contains a table with outstanding invoice references.
# 2. The table includes translated column headers (Reference, Date, Due Date, etc.).
# 3. No table is rendered when the partner has no outstanding invoices.

from odoo import Command, fields
from odoo.tests import tagged
from odoo.addons.account_followup.tests.common import TestAccountFollowupCommon


@tagged('post_install', '-at_install')
class TestFollowupInvoiceList(TestAccountFollowupCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['account_followup.followup.line'].search([]).unlink()
        cls.followup_line = cls.env['account_followup.followup.line'].create({
            'name': 'Test Level',
            'delay': 1,
            'send_email': True,
            'company_id': cls.company_data['company'].id,
        })
        cls.invoice = cls.env['account.move'].create({
            'move_type': 'out_invoice',
            'invoice_date': fields.Date.from_string('2020-01-01'),
            'invoice_date_due': fields.Date.from_string('2020-01-01'),
            'partner_id': cls.partner_a.id,
            'invoice_line_ids': [Command.create({
                'quantity': 1,
                'price_unit': 500,
                'tax_ids': [],
            })],
        })
        cls.invoice.action_post()

    def _get_followup_html(self, partner):
        report = self.env['account.followup.report']
        options = {
            'partner_id': partner.id,
            'followup_line': self.followup_line,
        }
        return str(report.with_context(mail=True).get_followup_report_html(options))

    def test_invoice_reference_in_email_body(self):
        """Follow-up email body contains the outstanding invoice reference."""
        html = self._get_followup_html(self.partner_a)
        self.assertIn(self.invoice.name, html)

    def test_column_headers_in_email_body(self):
        """Follow-up email body contains invoice table column headers."""
        html = self._get_followup_html(self.partner_a)
        self.assertIn('Due Date', html)

    def test_no_table_when_no_outstanding_invoices(self):
        """No invoice table is rendered when the partner has no outstanding invoices."""
        partner = self.env['res.partner'].create({'name': 'Clean Partner'})
        html = self._get_followup_html(partner)
        self.assertNotIn('<table', html)
