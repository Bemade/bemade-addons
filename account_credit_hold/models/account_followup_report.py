import base64

from markupsafe import Markup

from odoo import models, fields, api, _
from odoo.tools import float_is_zero


class FollowUpReport(models.AbstractModel):
    _inherit = 'account.followup.report'

    def _get_followup_report_options(self, partner, options=None):
        """
        Override to include credit hold information in followup report options.
        """
        res = super()._get_followup_report_options(partner, options)
        res.update({
            'credit_hold': partner.followup_line_id.account_hold if partner.followup_line_id else False,
            'partner_on_hold': partner.on_hold
        })
        return res

    def _generate_credit_hold_attachment(self, partner):
        """
        Generate PDF attachment for credit hold customers to be sent with followup emails.
        """
        if not partner.on_hold:
            return None

        # Generate the PDF report. Since Odoo 18 ``report_ref`` is the first
        # positional argument of ``_render_qweb_pdf``, so the report is passed by
        # xmlid and the record ids go to ``res_ids``.
        pdf_content, _dummy = self.env['ir.actions.report']._render_qweb_pdf(
            'account_credit_hold.account_credit_hold_report_action', [partner.id]
        )

        # Create attachment
        attachment = self.env['ir.attachment'].create({
            'name': f'Credit_Hold_Report_{partner.name.replace(" ", "_")}.pdf',
            'type': 'binary',
            'mimetype': 'application/pdf',
            'datas': base64.b64encode(pdf_content),
            'res_model': 'res.partner',
            'res_id': partner.id,
            'description': f'Credit hold report for {partner.name}'
        })

        return attachment

    def _send_email(self, options):
        """
        Override to include credit hold report as attachment for customers on hold.
        PDF is sent with EVERY followup email when customer is on credit hold.
        """
        partner = self.env['res.partner'].browse(options.get('partner_id'))

        # Generate credit hold attachment for ANY customer on credit hold (no configuration needed)
        if partner.on_hold:
            attachment = self._generate_credit_hold_attachment(partner)
            if attachment:
                # ``options['attachment_ids']`` is handed straight to
                # ``message_post(attachment_ids=...)`` by
                # ``account_followup``, which expects plain ids -- not ORM
                # command tuples. Copy rather than mutate the caller's list.
                attachment_ids = list(options.get('attachment_ids') or [])
                attachment_ids.append(attachment.id)
                options['attachment_ids'] = attachment_ids

        # Call the original method
        return super()._send_email(options)

    @api.model
    def _get_main_body(self, options):
        """
        Override to add credit hold information to email body.
        """
        partner = self.env['res.partner'].browse(options.get('partner_id'))
        # Capture on_hold BEFORE super(). super() reads followup_line_id, which
        # triggers _compute_followup_status, which auto-lifts the hold for any
        # partner that no longer warrants one -- so reading on_hold afterwards
        # can see False for a partner who was on hold when the email was built.
        was_on_hold = partner.on_hold
        body = super()._get_main_body(options)

        # Add credit hold notice if partner is on hold.
        # ``super()`` returns Markup, and ``Markup.__radd__`` escapes a plain
        # str operand -- so the notice must itself be Markup or its tags render
        # as literal text in the email.
        if was_on_hold:
            credit_hold_notice = Markup(_(
                "<div style='background-color: #fff3cd; border: 1px solid #ffeaa7; padding: 10px; margin: 10px 0; border-radius: 4px;'>"
                "<strong style='color: #856404;'>⚠️ Credit Hold Notice:</strong> "
                "Your account is currently on credit hold due to overdue invoices. "
                "Please settle the outstanding amounts to avoid service interruptions. "
                "Total amount due: <strong>%s</strong>"
                "</div>",
                partner.total_due
            ))
            body = credit_hold_notice + body

        return body
