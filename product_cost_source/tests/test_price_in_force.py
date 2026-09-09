# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html
"""Use case: a price inside an agreement in force is firm, whatever its age.

An eight-month-old price on an annual pricelist is not stale. The agreement
still binds the vendor, and age is irrelevant while it does.

ACCEPTANCE CRITERIA
1. A supplier price whose date_start/date_end bracket the requested date is
   Firm, however old date_start is.
2. Firmness is judged against the requested date, not against today.
3. A price whose date_end has passed is not in force, and falls through to
   age-based judgement.
4. A price whose date_start is in the future is not yet in force, and does not
   make the cost Firm.
5. An open-ended price (date_start set, no date_end) is in force from its start
   date onward. A vendor who set no end date has not promised an end.
6. A price with no dates at all is not "in force" -- there is no agreement to
   point at, only a number. It falls through to age-based judgement.
"""
from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.tests import tagged

from .common import ProductCostSourceCommon


@tagged("-at_install", "post_install")
class TestPriceInForce(ProductCostSourceCommon):
    def test_old_price_inside_agreement_is_firm(self):
        # Agreed 11 months ago, runs another month: far older than the 6-month
        # window, and firm anyway because the vendor is still bound by it.
        self._supplier_price(
            75.0,
            date_start=self._months_ago(11),
            date_end=fields.Date.today() + relativedelta(months=1),
        )
        resolution = self._resolve()
        self.assertEqual(resolution.confidence, "firm")
        self.assertTrue(resolution.sources[0].in_force)

    def test_firmness_judged_at_the_requested_date(self):
        start = self._months_ago(11)
        end = fields.Date.today() - relativedelta(months=1)
        self._supplier_price(75.0, date_start=start, date_end=end)
        # Asked about a date the agreement covered, it is firm.
        past = self._resolve(date=self._months_ago(6))
        self.assertEqual(past.confidence, "firm")
        # Asked about today, the agreement has lapsed and it is not.
        self.assertEqual(self._resolve().confidence, "estimated")

    def test_expired_agreement_is_not_in_force(self):
        self._supplier_price(
            75.0,
            date_start=self._months_ago(24),
            date_end=self._months_ago(12),
        )
        resolution = self._resolve()
        self.assertFalse(resolution.sources[0].in_force)
        self.assertEqual(resolution.confidence, "estimated")

    def test_future_agreement_is_not_yet_in_force(self):
        self._supplier_price(
            75.0,
            date_start=fields.Date.today() + relativedelta(months=1),
            date_end=fields.Date.today() + relativedelta(months=12),
        )
        resolution = self._resolve()
        self.assertFalse(resolution.sources[0].in_force)

    def test_open_ended_agreement_is_in_force(self):
        self._supplier_price(75.0, date_start=self._months_ago(24))
        resolution = self._resolve()
        self.assertTrue(resolution.sources[0].in_force)
        self.assertEqual(resolution.confidence, "firm")

    def test_undated_price_is_not_an_agreement(self):
        self._supplier_price(75.0)
        resolution = self._resolve()
        self.assertFalse(resolution.sources[0].in_force)
        self.assertAlmostEqual(resolution.unit_cost, 75.0)
        self.assertEqual(resolution.confidence, "estimated")
