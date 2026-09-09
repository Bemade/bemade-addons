# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html
from odoo import api, fields, models

PRICE_AGE_PARAM = "product_cost_source.price_age_months"
DEFAULT_PRICE_AGE_MONTHS = 6


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    price_age_months = fields.Integer(
        string="Price considered current for",
        default=DEFAULT_PRICE_AGE_MONTHS,
        config_parameter=PRICE_AGE_PARAM,
        help="How many months a price stays trustworthy once nothing else "
        "backs it up.\n\n"
        "This only applies outside a vendor agreement. A price covered by a "
        "date-bounded vendor pricelist is firm for as long as that agreement "
        "runs, however old the price is.\n\n"
        "Outside one, a price older than this is reported as an estimate, and "
        "the components responsible are named so they can be requoted.",
    )

    @api.model
    def _price_age_months(self):
        """The configured window, falling back to the default.

        Read through ``int()`` rather than trusted directly: the parameter is
        free text, and a blank or malformed value must not silently become a
        zero-month window that marks the whole catalogue stale.
        """
        raw = self.env["ir.config_parameter"].sudo().get_param(PRICE_AGE_PARAM)
        try:
            months = int(raw)
        except (TypeError, ValueError):
            return DEFAULT_PRICE_AGE_MONTHS
        return months if months > 0 else DEFAULT_PRICE_AGE_MONTHS
