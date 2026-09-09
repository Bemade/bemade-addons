# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html

from odoo import Command
from odoo.tests import tagged

from odoo.addons.base.tests.common import BaseCommon


@tagged("post_install", "-at_install", "product_pricelist_bom_cost")
class TestPricelistBomCost(BaseCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Product = cls.env["product.product"]
        # Two components with known standard prices.
        cls.comp_a = Product.create(
            {"name": "Component A", "type": "consu", "standard_price": 10.0}
        )
        cls.comp_b = Product.create(
            {"name": "Component B", "type": "consu", "standard_price": 5.0}
        )
        # Manufactured product with a BOM: 2 x A ($10) + 3 x B ($5) = $35.
        cls.finished = Product.create(
            {"name": "Manufactured Product", "type": "consu"}
        )
        cls.bom = cls.env["mrp.bom"].create(
            {
                "product_tmpl_id": cls.finished.product_tmpl_id.id,
                "product_id": cls.finished.id,
                "product_qty": 1.0,
                "type": "normal",
                "bom_line_ids": [
                    Command.create(
                        {"product_id": cls.comp_a.id, "product_qty": 2.0}
                    ),
                    Command.create(
                        {"product_id": cls.comp_b.id, "product_qty": 3.0}
                    ),
                ],
            }
        )
        # Product without any BOM (for the graceful-zero case).
        cls.no_bom_product = Product.create(
            {"name": "No BOM Product", "type": "consu", "standard_price": 99.0}
        )
        cls.pricelist = cls.env["product.pricelist"].create(
            {
                "name": "BOM Cost Pricelist",
                "item_ids": [
                    Command.create(
                        {
                            "compute_price": "formula",
                            "base": "bom_cost",
                            "price_discount": 0,
                            "min_quantity": 1.0,
                        },
                    )
                ],
            }
        )
        cls.item = cls.pricelist.item_ids[0]

    def test_bom_cost_passthrough(self):
        """BOM cost rollup is used verbatim when discount is 0."""
        self.assertAlmostEqual(
            self.pricelist._get_product_price(self.finished, 1),
            35.0,
        )

    def test_bom_cost_formula_markup(self):
        """The formula margin is applied on top of the BOM cost.

        price_discount = -25 -> 25% markup -> 35 * 1.25 = 43.75.
        """
        self.item.price_discount = -25
        self.assertAlmostEqual(
            self.pricelist._get_product_price(self.finished, 1),
            43.75,
        )

    def test_bom_cost_surcharge_and_round(self):
        """Surcharge and rounding from the formula chain apply to BOM cost.

        35 (cost) + 5 (surcharge), rounded to 1 -> 40.
        """
        self.item.write({"price_surcharge": 5, "price_round": 1})
        self.assertAlmostEqual(
            self.pricelist._get_product_price(self.finished, 1),
            40.0,
        )

    def test_bom_cost_min_margin(self):
        """price_min_margin floors the result at cost + margin.

        cost 35, discount 50% -> 17.5, but min_margin 10 floors at 35+10 = 45.
        """
        self.item.write(
            {"price_discount": 50, "price_min_margin": 10, "price_max_margin": 100}
        )
        self.assertAlmostEqual(
            self.pricelist._get_product_price(self.finished, 1),
            45.0,
        )

    def test_no_bom_returns_zero(self):
        """A product without a BOM yields a 0.0 BOM-cost price (no crash)."""
        price = self.no_bom_product.product_tmpl_id._get_bom_cost_pricelist_price(
            self.item
        )
        self.assertAlmostEqual(price, 0.0)

    def test_other_base_unaffected(self):
        """The override only fires for base='bom_cost'; other bases fall back.

        With base='list_price' the price must equal the native list-price
        compute, proving supplierinfo/list pricing is untouched.
        """
        self.item.base = "list_price"
        self.finished.product_tmpl_id.list_price = 123.0
        self.assertAlmostEqual(
            self.pricelist._get_product_price(self.finished, 1),
            123.0,
        )
