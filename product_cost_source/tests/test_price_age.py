# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html
"""Use case: outside an agreement, judge the last KNOWN price by its age.

With no agreement to lean on, all we have is when the price was last
established. How often the part is bought does not enter into it: a part
bought once every five years, on a two-year-old price, is out of date exactly
as a monthly part would be.

ACCEPTANCE CRITERIA
1. A price established within the timeout is Firm; one older is Estimated.
2. The timeout is configurable, and changing it moves the boundary.
3. The age is that of the last known price. The core module knows supplier
   price entries; other sources plug in (see test_extension_point).
4. write_date is NEVER the authority. A catalogue imported in bulk has one
   write_date for thousands of prices, which says when the import ran, not
   when anything was priced. A price whose age cannot be established is
   Estimated, not Firm -- unknown age is not evidence of freshness.
5. Boundary is inclusive: a price exactly at the timeout is still Firm.

These use lapsed agreements, which is the core module's only way to have a
dated price that is not in force. The other way -- a confirmed purchase -- is
contributed by the purchase plugin.
"""
from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.tests import tagged

from .common import ProductCostSourceCommon


@tagged("-at_install", "post_install")
class TestPriceAge(ProductCostSourceCommon):
    def _lapsed_price(self, price, agreed_months_ago):
        return self._supplier_price(
            price,
            date_start=self._months_ago(agreed_months_ago),
            date_end=fields.Date.today() - relativedelta(days=1),
        )

    def test_recent_price_is_firm(self):
        self._lapsed_price(75.0, 2)
        self.assertEqual(self._resolve().confidence, "firm")

    def test_aged_price_is_estimated(self):
        self._lapsed_price(75.0, 24)
        self.assertEqual(self._resolve().confidence, "estimated")

    def test_timeout_is_configurable(self):
        self._lapsed_price(75.0, 24)
        self.assertEqual(self._resolve().confidence, "estimated")
        self.env["ir.config_parameter"].sudo().set_param(
            "product_cost_source.price_age_months", "36"
        )
        self.assertEqual(self._resolve().confidence, "firm")

    def test_unknown_age_is_estimated_not_firm(self):
        # An undated price is the shape a bulk catalogue import leaves behind.
        # Its write_date would look recent; that must not make it Firm.
        seller = self._supplier_price(75.0)
        self.assertFalse(seller.date_start)
        resolution = self._resolve()
        self.assertIsNone(resolution.sources[0].priced_on)
        self.assertEqual(resolution.confidence, "estimated")

    def test_price_exactly_at_the_timeout_is_firm(self):
        self._lapsed_price(75.0, 6)
        self.assertEqual(self._resolve().confidence, "firm")
