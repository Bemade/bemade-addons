from odoo import fields, models

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
