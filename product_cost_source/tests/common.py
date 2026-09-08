# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html
"""Shared fixtures for the cost-source tests.

Deliberately minimal: each use case builds the prices and stock it needs, so
that a test reads as the situation it describes rather than as a lookup into
a shared pile of setup.
"""

from odoo.tests import TransactionCase


class ProductCostSourceCommon(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company = cls.env.company
        cls.vendor = cls.env["res.partner"].create({"name": "Test Vendor"})
        cls.other_vendor = cls.env["res.partner"].create({"name": "Other Vendor"})
        cls.product = cls.env["product.product"].create(
            {"name": "Test Component", "type": "consu", "is_storable": True}
        )

    def _supplier_price(self, price, product=None, partner=None, **values):
        """A supplier price entry; pass date_start/date_end/min_qty as needed."""
        product = product or self.product
        return self.env["product.supplierinfo"].create(
            {
                "partner_id": (partner or self.vendor).id,
                "product_tmpl_id": product.product_tmpl_id.id,
                "price": price,
                **values,
            }
        )

    def _resolve(self, qty=1.0, product=None, **kwargs):
        product = product or self.product
        return product._resolve_cost(qty=qty, **kwargs)

    def _set_stock_value(self, value, product=None):
        (product or self.product).standard_price = value

    def _months_ago(self, months):
        from dateutil.relativedelta import relativedelta
        from odoo import fields
        return fields.Date.today() - relativedelta(months=months)
