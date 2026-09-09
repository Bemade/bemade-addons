# -*- coding: utf-8 -*-
from odoo import _, api, fields, models
from odoo.exceptions import UserError


class MailForwardWizard(models.TransientModel):
    """Single dialog to forward one or more lost messages as a real
    outbound email (task 3965).

    This is deliberately narrow (To, From, optional note, "copy attachments"
    toggle, Send) rather than a full compose surface: it composes and sends
    through the shared ``mail.message._do_forward()`` helper, which is the
    single source of truth for outbound forward headers (From/Reply-To/
    threading). Contrast with Assign/Reassign, which stays a silent internal
    routing with no outbound mail.
    """
    _name = 'mail.forward.wizard'
    _description = 'Forward Message'

    message_ids = fields.Many2many('mail.message', string="Messages", required=True)
    email_to = fields.Char(
        string="To", required=True,
        help="Recipient email address(es), comma-separated.",
    )
    from_address_id = fields.Many2one(
        'mail.from.address',
        string="From",
        compute='_compute_from_address_id',
        readonly=False,
        store=True,
        help="Authorized address to send from. Falls back to the company/"
             "catchall address if none is selected.",
    )
    note = fields.Html(help="Optional note prepended above the quoted original message.")
    copy_attachments = fields.Boolean(default=True)

    @api.depends('message_ids')
    def _compute_from_address_id(self):
        for wizard in self:
            if wizard.from_address_id:
                continue
            allowed_addresses = self.env['mail.from.address']._get_allowed_addresses()
            wizard.from_address_id = allowed_addresses[0] if len(allowed_addresses) == 1 else False

    def action_forward(self):
        """Send the forward for every selected message and close the dialog."""
        self.ensure_one()
        if not self.email_to or not self.email_to.strip():
            raise UserError(_("Please enter at least one recipient to forward to."))

        for message in self.message_ids:
            message._do_forward(
                self.email_to,
                from_address=self.from_address_id,
                note=self.note,
                copy_attachments=self.copy_attachments,
            )

        return {'type': 'ir.actions.act_window_close'}
