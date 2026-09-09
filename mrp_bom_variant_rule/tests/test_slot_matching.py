# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html
"""Slot matching and rule precedence.

Acceptance criteria
===================

1. A ruleset decomposes a template into named slots. Generating a BOM for a
   variant emits at most one line per slot per matched rule.
2. Rules are evaluated per slot in ``sequence`` order; the FIRST rule whose
   attribute-value conditions are all satisfied by the variant wins. Later
   matching rules in the same slot are not applied.
3. A rule with no conditions matches every variant, and is therefore usable as
   a catch-all default when placed last in its slot's sequence.
4. A rule matches only if EVERY one of its condition sets is satisfied. Within
   one condition set (one attribute), the variant's value must be among those
   listed; across condition sets (different attributes), all must hold.
5. A non-required slot with no matching rule contributes no line and does not
   block generation.
6. Two rules in DIFFERENT slots both matching the same component product
   produce two separate lines, not a merged one. Slots are the unit of
   composition, not products.
7. Rules belonging to a ruleset not bound to the variant's template are never
   considered.
"""

from odoo.tests import tagged

from .builders import RuleSetBuilderMixin
from .common import BomVariantRuleCommon


@tagged("post_install", "-at_install", "mrp_bom_variant_rule")
class TestSlotMatching(BomVariantRuleCommon, RuleSetBuilderMixin):
    def test_single_matching_rule_emits_one_line(self):
        """Criterion 1."""
        rule_set = self._rule_set()
        slot = self._slot(rule_set, "Vessel")
        vessel = self._component("Vessel 10x54")
        self._rule(slot, vessel, qty_expr="1")

        variant = self._variant(self.size_large, self.count_single)
        bom = variant._bom_rule_generate()

        self.assertEqual(len(bom.bom_line_ids), 1)
        self.assertEqual(bom.bom_line_ids.product_id, vessel)
        self.assertEqual(bom.bom_line_ids.product_qty, 1.0)

    def test_first_rule_in_sequence_wins_within_slot(self):
        """Criterion 2."""
        rule_set = self._rule_set()
        slot = self._slot(rule_set, "Vessel")
        specific = self._component("Large Vessel")
        fallback = self._component("Any Vessel")
        # Both rules match a Large variant; only the earlier one may apply.
        self._rule(
            slot,
            specific,
            sequence=5,
            conditions=[(self.attr_size, self.size_large)],
        )
        self._rule(slot, fallback, sequence=10)

        variant = self._variant(self.size_large, self.count_single)
        bom = variant._bom_rule_generate()

        self.assertEqual(len(bom.bom_line_ids), 1)
        self.assertEqual(bom.bom_line_ids.product_id, specific)

    def test_unconditioned_rule_acts_as_catch_all(self):
        """Criterion 3."""
        rule_set = self._rule_set()
        slot = self._slot(rule_set, "Vessel")
        small_only = self._component("Small Vessel")
        catch_all = self._component("Default Vessel")
        self._rule(
            slot,
            small_only,
            sequence=5,
            conditions=[(self.attr_size, self.size_small)],
        )
        self._rule(slot, catch_all, sequence=99)

        large = self._variant(self.size_large, self.count_single)
        self.assertEqual(
            large._bom_rule_generate().bom_line_ids.product_id, catch_all
        )
        small = self._variant(self.size_small, self.count_single)
        self.assertEqual(
            small._bom_rule_generate().bom_line_ids.product_id, small_only
        )

    def test_all_condition_sets_must_hold(self):
        """Criterion 4."""
        rule_set = self._rule_set()
        slot = self._slot(rule_set, "Manifold", required=False)
        manifold = self._component("Twin Large Manifold")
        self._rule(
            slot,
            manifold,
            conditions=[
                (self.attr_size, self.size_large),
                (self.attr_count, self.count_twin),
            ],
        )

        half_match = self._variant(self.size_large, self.count_single)
        self.assertFalse(half_match._bom_rule_generate().bom_line_ids)

        full_match = self._variant(self.size_large, self.count_twin)
        self.assertEqual(
            full_match._bom_rule_generate().bom_line_ids.product_id, manifold
        )

    def test_value_within_condition_set_is_a_disjunction(self):
        """Criterion 4."""
        rule_set = self._rule_set()
        slot = self._slot(rule_set, "Vessel", required=False)
        vessel = self._component("Any Size Vessel")
        self._rule(
            slot,
            vessel,
            conditions=[
                (self.attr_size, self.size_small | self.size_large),
                (self.attr_count, self.count_twin),
            ],
        )

        for size in (self.size_small, self.size_large):
            variant = self._variant(size, self.count_twin)
            self.assertEqual(
                variant._bom_rule_generate().bom_line_ids.product_id,
                vessel,
                "either listed size should satisfy the condition set",
            )
        single = self._variant(self.size_small, self.count_single)
        self.assertFalse(single._bom_rule_generate().bom_line_ids)

    def test_unmatched_optional_slot_is_skipped(self):
        """Criterion 5."""
        rule_set = self._rule_set()
        vessel_slot = self._slot(rule_set, "Vessel", sequence=10)
        vessel = self._component("Vessel")
        self._rule(vessel_slot, vessel)

        bypass_slot = self._slot(
            rule_set, "Bypass", sequence=20, required=False
        )
        bypass = self._component("Bypass Kit")
        self._rule(
            bypass_slot,
            bypass,
            conditions=[(self.attr_count, self.count_twin)],
        )

        variant = self._variant(self.size_small, self.count_single)
        bom = variant._bom_rule_generate()

        self.assertTrue(bom)
        self.assertEqual(bom.bom_line_ids.product_id, vessel)

    def test_same_component_in_two_slots_yields_two_lines(self):
        """Criterion 6."""
        rule_set = self._rule_set()
        gasket = self._component("Gasket")
        top = self._slot(rule_set, "Top Port", sequence=10)
        bottom = self._slot(rule_set, "Bottom Port", sequence=20)
        self._rule(top, gasket, qty_expr="1")
        self._rule(bottom, gasket, qty_expr="2")

        variant = self._variant(self.size_small, self.count_single)
        bom = variant._bom_rule_generate()

        self.assertEqual(len(bom.bom_line_ids), 2)
        self.assertEqual(bom.bom_line_ids.product_id, gasket)
        self.assertEqual(
            sorted(bom.bom_line_ids.mapped("product_qty")), [1.0, 2.0]
        )

    def test_rules_from_unbound_ruleset_are_ignored(self):
        """Criterion 7."""
        bound = self._rule_set(name="Bound")
        vessel = self._component("Vessel")
        self._rule(self._slot(bound, "Vessel"), vessel)

        other_template = self.env["product.template"].create(
            {"name": "Unrelated", "type": "consu"}
        )
        unbound = self._rule_set(name="Unbound", templates=other_template)
        intruder = self._component("Intruder")
        self._rule(self._slot(unbound, "Intruder"), intruder)

        variant = self._variant(self.size_small, self.count_single)
        bom = variant._bom_rule_generate()

        self.assertEqual(bom.bom_line_ids.product_id, vessel)
        self.assertEqual(bom.generated_rule_set_id, bound)
