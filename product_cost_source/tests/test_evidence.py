# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html
"""Use case: say what is known and what is not, per source.

The point of the module. A person quoting needs to know which numbers to
trust and which to requote, and a bare "Estimated" does not tell them.

ACCEPTANCE CRITERIA
1. Every resolved cost carries evidence naming each contributing source.
2. An in-force agreement names its expiry.
3. An aged price names its age and the last thing that established it.
4. Stock coverage says so.
5. A blend names both contributions and how much each covered, so the reader
   can see the split rather than a single opaque average.
6. Evidence is translatable and contains no developer vocabulary -- no field
   names, no model names, no source keys.
7. A product with nothing known says so plainly rather than returning empty
   evidence next to a confident-looking zero.
"""
from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.tests import tagged

from .common import ProductCostSourceCommon


@tagged("-at_install", "post_install")
class TestEvidence(ProductCostSourceCommon):
    def test_every_source_is_named(self):
        self._set_stock_value(10.0)
        self._supplier_price(15.0)
        resolution = self._resolve(qty=60, qty_from_stock=40)
        self.assertEqual(len(resolution.evidence), len(resolution.sources))

    def test_in_force_agreement_names_its_expiry(self):
        expiry = fields.Date.today() + relativedelta(months=3)
        self._supplier_price(75.0, date_start=self._months_ago(9), date_end=expiry)
        sentence = self._resolve().evidence[0]
        self.assertIn("firm", sentence.lower())
        self.assertIn(fields.Date.to_string(expiry), sentence)

    def test_aged_price_names_its_age_and_last_event(self):
        agreed = self._months_ago(24)
        self._supplier_price(
            75.0,
            date_start=agreed,
            date_end=fields.Date.today() - relativedelta(days=1),
        )
        sentence = self._resolve().evidence[0]
        self.assertIn("6 months old", sentence)
        self.assertIn(fields.Date.to_string(agreed), sentence)

    def test_stock_coverage_is_stated(self):
        self._set_stock_value(10.0)
        sentence = self._resolve(qty=5, qty_from_stock=5).evidence[0]
        self.assertIn("stock", sentence.lower())

    def test_blend_names_both_contributions(self):
        self._set_stock_value(10.0)
        self._supplier_price(15.0)
        resolution = self._resolve(qty=60, qty_from_stock=40)
        joined = " ".join(resolution.evidence)
        self.assertIn("40", joined)
        self.assertIn("20", joined)
        self.assertIn("60", joined)

    def test_nothing_known_says_so(self):
        resolution = self._resolve()
        self.assertEqual(len(resolution.evidence), 1)
        self.assertIn("no", resolution.evidence[0].lower())

    def test_evidence_carries_no_developer_vocabulary(self):
        self._set_stock_value(10.0)
        self._supplier_price(15.0, date_start=self._months_ago(1))
        for sentence in self._resolve(qty=60, qty_from_stock=40).evidence:
            for jargon in (
                "date_start",
                "date_end",
                "write_date",
                "standard_price",
                "supplierinfo",
                "product.product",
                "priced_on",
                "in_force",
            ):
                self.assertNotIn(jargon, sentence)
