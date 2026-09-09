from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    delivery_notification_recipient = fields.Selection(
        related="company_id.delivery_notification_recipient",
        readonly=False,
    )