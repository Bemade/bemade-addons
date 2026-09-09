# -*- coding: utf-8 -*-
from odoo import api, fields, models


class MailFinanceTriageWizard(models.TransientModel):
    """Wizard for triaging finance-related lost messages."""
    _name = 'mail.finance.triage.wizard'
    _description = 'Finance Triage Wizard'

    message_ids = fields.Many2many('mail.message', string="Messages")
    action = fields.Selection([
        ('helpdesk', 'Create Helpdesk Ticket'),
        ('forward', 'Forward to Email'),
    ], default='forward', required=True)

    # Helpdesk availability (overridden by mail_manual_routing_helpdesk)
    has_helpdesk = fields.Boolean(compute='_compute_has_helpdesk')

    # Forward fields
    forward_email = fields.Char(string="Forward To")

    @api.depends_context('uid')
    def _compute_has_helpdesk(self):
        """Check if helpdesk is available. Overridden by bridge module."""
        for wizard in self:
            wizard.has_helpdesk = False

    def action_triage(self):
        """Execute the selected triage action."""
        self.ensure_one()

        if self.action == 'helpdesk' and self.has_helpdesk:
            return self._create_helpdesk_tickets()
        elif self.action == 'forward':
            return self._forward_messages()

        return {'type': 'ir.actions.act_window_close'}

    def _create_helpdesk_tickets(self):
        """Create helpdesk tickets. Implemented by bridge module."""
        return {'type': 'ir.actions.act_window_close'}

    def _forward_messages(self):
        """Forward messages to the specified email address.

        Delegates the actual send to the shared ``mail.message._do_forward()``
        helper (task 3965) so this path gets the corrected From/Reply-To/
        threading headers instead of the old crude, unauthenticated send.
        ``mark_forwarded=False`` is passed because this wizard applies its
        own "Finance" subcategory below.
        """
        if not self.forward_email:
            return {'type': 'ir.actions.act_window_close'}

        for message in self.message_ids:
            message._do_forward(self.forward_email, mark_forwarded=False)

        # Mark messages as processed
        subcategory = self.env.ref('mail_manual_routing_ux.subcategory_finance', raise_if_not_found=False)
        if subcategory:
            self.message_ids.write({'lost_subcategory_id': subcategory.id})

        return {'type': 'ir.actions.act_window_close'}
