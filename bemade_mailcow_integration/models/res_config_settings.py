from odoo import fields, models, api, _
from odoo.exceptions import ValidationError


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    mailcow_base_url = fields.Char(
        string="Mailcow Base URL",
        help="URL for the Mailcow server API",
        config_parameter='mailcow.base_url',
    )
    mailcow_api_key = fields.Char(
        string="Mailcow API Key",
        help="API key for the Mailcow server",
        config_parameter='mailcow.api_key',
    )

    mailcow_sync_alias = fields.Boolean(
        string='Sync Aliases with Odoo',
        help='Auto create Aliases in Mailcow from Odoo',
        config_parameter='mailcow.sync_alias')

    mailcow_auto_create = fields.Boolean(
        string='Create Mailboxes in Mailcow',
        help='Auto create Mailboxes in Mailcow on creation in Odoo',
        config_parameter='mailcow.create_mailbox')

    @api.constrains('mailcow_sync_alias', 'mailcow_auto_create')
    def require_api_key_and_base_url_to_sync(self):
        if not self.mailcow_api_key and self.mailcow_base_url:
            raise ValidationError(_("You must set a base URL and API key to enable synchronization."))
