# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html
"""Use case: cost what stock can cover at stock valuation.

Stock already owned was paid for at a known price. When it covers the demand,
that price is what the goods cost us -- not what replacing them would cost.

ACCEPTANCE CRITERIA
1. Demand fully covered by stock resolves at the product's stock valuation.
2. Demand with no stock at all resolves at the vendor price.
3. Demand partly covered blends the two, weighted by quantity: 40 of 60 from
   stock at 10 and 20 from a vendor at 15 resolves to 11.67 per unit.
4. The blend divides by the quantity actually being costed, so the weights sum
   back to that quantity. A partially delivered demand is costed on what
   remains, and the two never mix bases.
5. Negative stock on hand counts as no coverage, never as negative coverage.
6. Partial coverage with no price for the remainder costs what IS known,
   rather than averaging a known cost against an unpriced gap. Costing 40
   units of stock at 10 across a demand of 60 would report 6.67 -- cheaper
   than anything we own, because the 20 we cannot price were counted as free.
7. Coverage is supplied by the caller, not discovered here. This module does
   not know what a demand is -- a sale line, a manufacturing order and a
   forecast all reason about availability differently.
"""
from odoo.tests import tagged

from .common import ProductCostSourceCommon


@tagged("-at_install", "post_install")
class TestStockCoverage(ProductCostSourceCommon):
    def test_full_coverage_uses_stock_valuation(self):
        self._set_stock_value(10.0)
        self._supplier_price(15.0)
        resolution = self._resolve(qty=60, qty_from_stock=60)
        self.assertAlmostEqual(resolution.unit_cost, 10.0)
        self.assertEqual([s.key for s in resolution.sources], ["stock"])

    def test_no_coverage_uses_vendor_price(self):
        self._set_stock_value(10.0)
        self._supplier_price(15.0)
        resolution = self._resolve(qty=60, qty_from_stock=0)
        self.assertAlmostEqual(resolution.unit_cost, 15.0)
        self.assertEqual([s.key for s in resolution.sources], ["vendor"])

    def test_partial_coverage_blends_weighted_by_quantity(self):
        self._set_stock_value(10.0)
        self._supplier_price(15.0)
        resolution = self._resolve(qty=60, qty_from_stock=40)
        # (40 * 10 + 20 * 15) / 60
        self.assertAlmostEqual(resolution.unit_cost, 11.67, places=2)
        self.assertEqual(
            sorted(s.key for s in resolution.sources), ["stock", "vendor"]
        )

    def test_blend_weights_sum_to_the_costed_quantity(self):
        self._set_stock_value(10.0)
        self._supplier_price(15.0)
        resolution = self._resolve(qty=60, qty_from_stock=40)
        self.assertAlmostEqual(sum(s.qty for s in resolution.sources), 60.0)
        # Coverage exceeding the demand cannot inflate the weights either: a
        # caller costing what remains of a partly delivered order must not be
        # able to push the total past the quantity it asked about.
        clamped = self._resolve(qty=20, qty_from_stock=500)
        self.assertAlmostEqual(sum(s.qty for s in clamped.sources), 20.0)
        self.assertAlmostEqual(clamped.unit_cost, 10.0)

    def test_unpriced_remainder_does_not_dilute_the_known_cost(self):
        self._set_stock_value(10.0)
        self.assertFalse(self.product.seller_ids)
        resolution = self._resolve(qty=60, qty_from_stock=40)
        # Only the 40 we can price are costed; the gap is not counted as free.
        self.assertAlmostEqual(resolution.unit_cost, 10.0)
        self.assertEqual([s.key for s in resolution.sources], ["stock"])

    def test_negative_on_hand_is_no_coverage(self):
        self._set_stock_value(10.0)
        self._supplier_price(15.0)
        resolution = self._resolve(qty=60, qty_from_stock=-40)
        self.assertAlmostEqual(resolution.unit_cost, 15.0)
        self.assertEqual([s.key for s in resolution.sources], ["vendor"])
