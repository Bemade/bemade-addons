# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html
"""Use case: resolve a unit cost from the vendor pricelist.

ACCEPTANCE CRITERIA
1. With one supplier price and no stock, the resolved unit cost is that price.
2. When several supplier prices apply, the one Odoo itself would pick wins
   (sequence order), so we never disagree with the purchase flow.
3. A supplier price in a foreign currency is converted to the requested
   currency at the requested date, not at today's rate.
4. Quantity is respected: a price with a min_qty that the demand does not
   reach is not used; one whose min_qty it does reach is.
5. A product with no supplier price at all resolves to no vendor source
   rather than to a cost of zero. Zero is a price; "unknown" is not.
"""
from odoo.tests import tagged

from .common import ProductCostSourceCommon


@tagged("-at_install", "post_install")
class TestVendorPrice(ProductCostSourceCommon):
    def test_single_supplier_price_is_the_cost(self):
        self._supplier_price(75.0)
        self.assertAlmostEqual(self._resolve().unit_cost, 75.0)

    def test_supplier_sequence_decides(self):
        self._supplier_price(90.0, partner=self.other_vendor, sequence=20)
        self._supplier_price(75.0, sequence=1)
        resolution = self._resolve()
        self.assertAlmostEqual(resolution.unit_cost, 75.0)
        self.assertEqual([s.key for s in resolution.sources], ["vendor"])

    def test_foreign_currency_converted_at_the_given_date(self):
        usd = self.env.ref("base.USD")
        company_currency = self.env.company.currency_id
        if usd == company_currency:
            self.skipTest("company currency is USD; conversion is a no-op")
        self.env["res.currency.rate"].create(
            {
                "name": self._months_ago(1),
                "currency_id": usd.id,
                "company_id": self.env.company.id,
                "rate": 2.0,
            }
        )
        self._supplier_price(100.0, currency_id=usd.id)
        # 100 USD at 2 USD per unit of company currency == 50.
        self.assertAlmostEqual(self._resolve().unit_cost, 50.0, places=2)

    def test_min_qty_gates_the_price(self):
        self._supplier_price(50.0, min_qty=100)
        self._supplier_price(80.0, min_qty=1, sequence=5)
        # Demand of 10 cannot reach the bulk break, so the bulk price is not used.
        self.assertAlmostEqual(self._resolve(qty=10).unit_cost, 80.0)
        # Demand of 100 reaches it.
        self.assertAlmostEqual(self._resolve(qty=100).unit_cost, 50.0)

    def test_no_supplier_price_is_unknown_not_zero(self):
        resolution = self._resolve()
        self.assertEqual(resolution.sources, [])
        self.assertEqual(resolution.confidence, "unknown")
        self.assertFalse(resolution.is_firm)
        self.assertTrue(resolution.evidence, "silence is not an answer")
