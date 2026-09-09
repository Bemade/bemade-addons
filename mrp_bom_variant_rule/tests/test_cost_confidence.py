# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html
"""Cost confidence: stale inputs stay visible as stale.

This module prices nothing. It records how trustworthy the component prices
underneath a generated BOM are, so a rollup built on stale inputs does not
present itself as a firm number — and so the gaps double as a repricing
worklist.

Acceptance criteria
===================

1. Generation records, per generated BOM, which component products carry NO
   vendor price at all.
2. It records which carry a vendor price older than a configurable maximum age.
3. The BOM exposes an overall confidence derived from its components: firm
   when every component has a current price, otherwise estimated.
4. The stored detail names the offending COMPONENTS, not just a count, so the
   result is directly actionable as a repricing list.
5. Confidence is recomputed on regeneration and does not go stale silently
   after component prices are updated.
6. A component with a current vendor price on a DIFFERENT vendor than the
   preferred one still counts as priced. The question is whether a price
   exists, not which vendor won.
7. Degraded confidence never blocks generation. It is information, not a gate —
   an approximate BOM is the "massive step up" over no BOM; refusing to
   generate because prices are old would defeat the purpose.
8. An empty ruleset result cannot report firm confidence — confidence is only
   meaningful about components actually present.
"""

from datetime import timedelta

from odoo import fields
from odoo.tests import tagged

from .builders import RuleSetBuilderMixin
from .common import BomVariantRuleCommon


@tagged("post_install", "-at_install", "mrp_bom_variant_rule")
class TestCostConfidence(BomVariantRuleCommon, RuleSetBuilderMixin):
    def setUp(self):
        super().setUp()
        self.vendor = self.env["res.partner"].create({"name": "Main Vendor"})
        self.other_vendor = self.env["res.partner"].create(
            {"name": "Second Vendor"}
        )
        self.rule_set = self._rule_set()
        self.vessel = self._component("Vessel")
        self.resin = self._component("Resin")
        self.valve = self._component("Valve")
        for sequence, component in enumerate(
            (self.vessel, self.resin, self.valve), start=1
        ):
            self._rule(
                self._slot(
                    self.rule_set, component.name, sequence=sequence * 10
                ),
                component,
                qty_expr="1",
            )
        self.variant = self._variant(self.size_small, self.count_single)

    def _price(self, component, age_days=0, vendor=None, sequence=1):
        """Give ``component`` a vendor price quoted ``age_days`` ago."""
        return self.env["product.supplierinfo"].create(
            {
                "partner_id": (vendor or self.vendor).id,
                "product_tmpl_id": component.product_tmpl_id.id,
                "price": 100.0,
                "sequence": sequence,
                "date_start": fields.Date.today() - timedelta(days=age_days),
            }
        )

    def _set_max_age(self, days):
        self.env["ir.config_parameter"].sudo().set_param(
            "mrp_bom_variant_rule.max_price_age_days", str(days)
        )

    # ------------------------------------------------------------------
    # Criterion 1
    # ------------------------------------------------------------------
    def test_unpriced_components_are_recorded(self):
        """Criterion 1."""
        self._price(self.vessel)
        self._price(self.valve)

        bom = self.variant._bom_rule_generate()

        self.assertEqual(bom.cost_unpriced_product_ids, self.resin)
        self.assertNotIn(self.vessel, bom.cost_unpriced_product_ids)
        self.assertNotIn(self.valve, bom.cost_unpriced_product_ids)

    # ------------------------------------------------------------------
    # Criterion 2
    # ------------------------------------------------------------------
    def test_stale_priced_components_are_recorded(self):
        """Criterion 2."""
        self._price(self.vessel)
        self._price(self.resin, age_days=400)
        self._price(self.valve, age_days=60)

        bom = self.variant._bom_rule_generate()

        # Under the default maximum age a year-old price is stale and a
        # two-month-old one is not.
        self.assertEqual(bom.cost_stale_priced_product_ids, self.resin)
        self.assertFalse(bom.cost_unpriced_product_ids)

        # The threshold is configuration, not a constant: tighten it and the
        # two-month-old price falls out of tolerance too.
        self._set_max_age(30)
        bom = self.variant._bom_rule_generate(force=True)

        self.assertEqual(
            bom.cost_stale_priced_product_ids, self.resin | self.valve
        )

    # ------------------------------------------------------------------
    # Criterion 3
    # ------------------------------------------------------------------
    def test_overall_confidence_reflects_components(self):
        """Criterion 3."""
        for component in (self.vessel, self.resin, self.valve):
            self._price(component)

        bom = self.variant._bom_rule_generate()
        self.assertEqual(bom.cost_confidence, "firm")

        # One missing price is enough to withdraw the claim.
        self.resin.seller_ids.unlink()
        bom = self.variant._bom_rule_generate(force=True)
        self.assertEqual(bom.cost_confidence, "estimated")

        # As is one price that is merely too old.
        self._price(self.resin, age_days=400)
        bom = self.variant._bom_rule_generate(force=True)
        self.assertEqual(bom.cost_confidence, "estimated")

    # ------------------------------------------------------------------
    # Criterion 4
    # ------------------------------------------------------------------
    def test_detail_names_offending_components(self):
        """Criterion 4."""
        self._price(self.vessel)
        self._price(self.valve, age_days=400)

        bom = self.variant._bom_rule_generate()

        # A count would say "two components need attention" and leave whoever
        # reads it to go find out which. The point is the worklist.
        self.assertEqual(bom.cost_unpriced_product_ids, self.resin)
        self.assertEqual(bom.cost_stale_priced_product_ids, self.valve)

    # ------------------------------------------------------------------
    # Criterion 5
    # ------------------------------------------------------------------
    def test_confidence_recomputed_on_regeneration(self):
        """Criterion 5."""
        self._price(self.vessel)
        self._price(self.valve)

        bom = self.variant._bom_rule_generate()
        self.assertEqual(bom.cost_confidence, "estimated")
        self.assertEqual(bom.cost_unpriced_product_ids, self.resin)

        self._price(self.resin)
        regenerated = self.variant._bom_rule_generate(force=True)

        self.assertEqual(regenerated, bom)
        self.assertEqual(regenerated.cost_confidence, "firm")
        self.assertFalse(regenerated.cost_unpriced_product_ids)
        self.assertFalse(regenerated.cost_stale_priced_product_ids)

    # ------------------------------------------------------------------
    # Criterion 6
    # ------------------------------------------------------------------
    def test_non_preferred_vendor_price_counts_as_priced(self):
        """Criterion 6."""
        self._price(self.vessel)
        self._price(self.valve)
        # The preferred vendor's quote has gone stale, but a second vendor
        # quoted the same part this week. The component is priced.
        self._price(self.resin, age_days=400, vendor=self.vendor, sequence=1)
        self._price(
            self.resin, age_days=1, vendor=self.other_vendor, sequence=5
        )

        bom = self.variant._bom_rule_generate()

        self.assertNotIn(self.resin, bom.cost_unpriced_product_ids)
        self.assertNotIn(self.resin, bom.cost_stale_priced_product_ids)
        self.assertEqual(bom.cost_confidence, "firm")

    # ------------------------------------------------------------------
    # Criterion 7
    # ------------------------------------------------------------------
    def test_estimated_cost_basis_does_not_block_generation(self):
        """Criterion 7."""
        # Nothing at all is priced: the worst case the rules can hand us.
        bom = self.variant._bom_rule_generate()

        self.assertTrue(bom)
        self.assertEqual(bom.cost_confidence, "estimated")
        self.assertEqual(
            sorted(bom.bom_line_ids.mapped("product_id.name")),
            ["Resin", "Valve", "Vessel"],
        )
        self.assertEqual(
            bom.cost_unpriced_product_ids,
            self.vessel | self.resin | self.valve,
        )
        # And the BOM is the variant's real one, not a placeholder held back.
        self.assertEqual(self.variant._bom_rule_bom(), bom)

    # ------------------------------------------------------------------
    # Criterion 8
    # ------------------------------------------------------------------
    def test_empty_result_is_not_firm(self):
        """Criterion 8."""
        empty_set = self._rule_set(name="Empty Ruleset")
        # An optional slot nothing matches is the legitimate way to arrive at
        # a bill of materials with no lines.
        self._slot(empty_set, "Optional Extra", sequence=10, required=False)
        self.rule_set.active = False

        bom = self.variant._bom_rule_generate()

        self.assertTrue(bom)
        self.assertFalse(bom.bom_line_ids)
        self.assertNotEqual(bom.cost_confidence, "firm")
