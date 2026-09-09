# Copyright 2025 Bemade Inc.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import api, fields, models


class MailComposeMessage(models.TransientModel):
    _inherit = "mail.compose.message"

    from_address_id = fields.Many2one(
        "mail.from.address",
        string="From Address",
        help="Select which authorized email address to use as the From address",
        compute="_compute_from_address_id",
        readonly=False,
        store=True,
    )

    @api.depends("composition_mode")
    def _compute_from_address_id(self):
        """Set default From address if the user has exactly one allowed address."""
        for composer in self:
            if composer.from_address_id:
                continue
            allowed_addresses = self.env["mail.from.address"]._get_allowed_addresses()
            if len(allowed_addresses) == 1:
                composer.from_address_id = allowed_addresses[0]
            else:
                composer.from_address_id = False

    def _action_send_mail_comment(self, res_ids):
        """Override to use from_address_id email when sending."""
        self.ensure_one()
        if self.from_address_id:
            self.email_from = self.from_address_id.email
        return super()._action_send_mail_comment(res_ids)
