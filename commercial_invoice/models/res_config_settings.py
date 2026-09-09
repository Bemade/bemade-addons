# License: LGPL-3
# Author: Bemade Inc. (Marc Durepos <marc@bemade.org>)
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    commercial_invoice_show_default_code = fields.Boolean(
        string="Show Internal Reference on Commercial Invoice",
        config_parameter="commercial_invoice.show_default_code",
        default=True,
    )
