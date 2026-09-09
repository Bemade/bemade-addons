from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    require_delivery_billing_mode = fields.Boolean(
        string="Require Delivery Billing Mode",
        help="When enabled, a delivery billing mode must be set on sale orders before they can be confirmed.",
        config_parameter="delivery_carrier_partner_account.require_delivery_billing_mode",
    )
