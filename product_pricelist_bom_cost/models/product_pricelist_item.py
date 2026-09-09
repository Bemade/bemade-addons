# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html

from odoo import fields, models


class ProductPricelistItem(models.Model):
    _inherit = "product.pricelist.item"

    base = fields.Selection(
        selection_add=[("bom_cost", "Prices based on BOM cost")],
        ondelete={"bom_cost": "set default"},
    )

    def _compute_price(self, product, quantity, uom, date, currency=None):
        result = super()._compute_price(product, quantity, uom, date, currency)
        context = self.env.context
        if self.compute_price == "formula" and self.base == "bom_cost":
            result = product.sudo()._get_bom_cost_pricelist_price(
                self,
                date=date or context.get("date", fields.Date.today()),
                quantity=quantity,
            )
        return result
