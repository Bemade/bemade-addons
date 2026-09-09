# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html

from odoo import models


class ProductProduct(models.Model):
    _inherit = "product.product"

    def _get_bom_cost_pricelist_price(self, rule, date=None, quantity=None):
        return self.product_tmpl_id._get_bom_cost_pricelist_price(
            rule, date=date, quantity=quantity, product_id=self.id
        )

    def _price_compute(
        self, price_type, uom=None, currency=None, company=None, date=False
    ):
        """Return a dummy not-falsy price when the base is the BOM cost, so the
        native ``_compute_base_price`` does not raise on the unknown
        ``bom_cost`` price_type. The real value is filled in afterwards by
        ``product.pricelist.item._compute_price``. Mirrors
        ``product_pricelist_supplierinfo``.
        """
        if price_type == "bom_cost":
            return dict.fromkeys(self.ids, 1.0)
        return super()._price_compute(
            price_type, uom=uom, currency=currency, company=company, date=date
        )
