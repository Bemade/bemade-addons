# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html
"""Use case: warn when the price will have expired by the time we deliver.

Quoting today against an agreement that lapses next week, for delivery in two
months, is quoting a price we will not get. This is the case a plain age check
cannot see, because the price is firm *now*.

ACCEPTANCE CRITERIA
1. An agreement in force at the quote date but expired at the delivery date
   produces a warning naming both dates.
2. An agreement covering the delivery date produces no warning.
3. No delivery date supplied means no warning -- silence, not a guess.
4. The warning does not change the cost or the confidence. The price is firm
   today; the warning says it will not stay so.
"""
from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.tests import tagged

from .common import ProductCostSourceCommon


@tagged("-at_install", "post_install")
class TestExpiryWarning(ProductCostSourceCommon):
    def setUp(self):
        super().setUp()
        self.expiry = fields.Date.today() + relativedelta(days=7)
        self._supplier_price(
            75.0, date_start=self._months_ago(6), date_end=self.expiry
        )

    def test_expiry_before_delivery_warns(self):
        delivery = fields.Date.today() + relativedelta(months=2)
        resolution = self._resolve(delivery_date=delivery)
        self.assertEqual(len(resolution.warnings), 1)
        warning = resolution.warnings[0]
        self.assertIn(fields.Date.to_string(self.expiry), warning)
        self.assertIn(fields.Date.to_string(delivery), warning)

    def test_agreement_covering_delivery_does_not_warn(self):
        delivery = fields.Date.today() + relativedelta(days=2)
        self.assertEqual(self._resolve(delivery_date=delivery).warnings, [])

    def test_no_delivery_date_no_warning(self):
        self.assertEqual(self._resolve().warnings, [])

    def test_warning_does_not_alter_cost_or_confidence(self):
        delivery = fields.Date.today() + relativedelta(months=2)
        quiet = self._resolve()
        loud = self._resolve(delivery_date=delivery)
        self.assertEqual(loud.confidence, quiet.confidence)
        self.assertEqual(loud.confidence, "firm")
        self.assertAlmostEqual(loud.unit_cost, quiet.unit_cost)
        self.assertTrue(loud.warnings)
