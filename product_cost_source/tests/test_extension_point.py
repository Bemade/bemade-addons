# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html
"""Use case: other modules contribute cost sources.

This is what keeps `purchase` out of the core. Purchase-order history is a
better authority on the last known price than a supplier price record, but
not every installation has purchase, so it plugs in.

Note the contract these tests pin down: contributed price evidence *competes*
with the built-in supplier price rather than accumulating beside it. They are
answering the same question -- what would a vendor charge -- so the
best-evidenced answer wins. Coverage sources (stock, vendor) accumulate; price
evidence competes.

ACCEPTANCE CRITERIA
1. Overriding _cost_source_price_candidates() and appending evidence makes it
   participate in resolution, confidence and evidence with no further wiring.
2. A contributed source can win: a more recent one supersedes the supplier
   price as the last known price.
3. A contributed source can be the only source, for a product with no supplier
   price at all.
4. Contributed sources are ordered by the same rule as built-in ones, so a
   plugin cannot jump the queue merely by being a plugin.
5. Removing the override restores the previous result exactly -- the extension
   point adds, and does not perturb, the base behaviour.
"""
from unittest.mock import patch

from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.tests import tagged

from ..tools.cost_source import CostSource
from .common import ProductCostSourceCommon


@tagged("-at_install", "post_install")
class TestExtensionPoint(ProductCostSourceCommon):
    def _contributing(self, price, priced_on, in_force=False):
        """Patch in a plugin that contributes one piece of price evidence."""
        model = type(self.env["product.product"])
        base = model._cost_source_price_candidates

        def patched(record, qty, date, currency, company):
            candidates = base(record, qty, date, currency, company)
            candidates.append(
                CostSource(
                    key="vendor",
                    qty=qty,
                    unit_price=price,
                    priced_on=priced_on,
                    in_force=in_force,
                )
            )
            return candidates

        return patch.object(model, "_cost_source_price_candidates", patched)

    def test_contributed_source_participates(self):
        self._supplier_price(75.0)
        with self._contributing(60.0, self._months_ago(1)):
            resolution = self._resolve()
        # Dated evidence outranks the undated supplier price.
        self.assertAlmostEqual(resolution.unit_cost, 60.0)
        self.assertEqual(resolution.confidence, "firm")

    def test_more_recent_contributed_source_wins(self):
        self._supplier_price(
            75.0,
            date_start=self._months_ago(24),
            date_end=fields.Date.today() - relativedelta(days=1),
        )
        with self._contributing(60.0, self._months_ago(2)):
            resolution = self._resolve()
        self.assertAlmostEqual(resolution.unit_cost, 60.0)
        self.assertEqual(resolution.confidence, "firm")

    def test_contributed_source_can_be_the_only_one(self):
        self.assertFalse(self.product.seller_ids)
        with self._contributing(60.0, self._months_ago(2)):
            resolution = self._resolve()
        self.assertAlmostEqual(resolution.unit_cost, 60.0)
        self.assertEqual(len(resolution.sources), 1)

    def test_contributed_sources_obey_the_same_ordering(self):
        # An in-force agreement outranks more recent loose evidence: a promise
        # beats an observation, whoever supplied it.
        self._supplier_price(
            75.0,
            date_start=self._months_ago(9),
            date_end=fields.Date.today() + relativedelta(months=3),
        )
        with self._contributing(60.0, fields.Date.today()):
            resolution = self._resolve()
        self.assertAlmostEqual(resolution.unit_cost, 75.0)

    def test_base_behaviour_unperturbed(self):
        self._supplier_price(75.0, date_start=self._months_ago(1))
        before = self._resolve()
        with self._contributing(60.0, self._months_ago(2)):
            self._resolve()
        after = self._resolve()
        self.assertAlmostEqual(after.unit_cost, before.unit_cost)
        self.assertEqual(after.confidence, before.confidence)
        self.assertEqual(after.evidence, before.evidence)
