# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html
"""Refusal over silent incompleteness.

A partially populated BOM that under-costs a quotation is a worse outcome than
no BOM at all. This file pins that down.

Acceptance criteria
===================

1. If a slot flagged ``required`` has no matching rule for a variant,
   generation raises rather than returning a BOM.
2. The error names the unmatched slot AND the variant's attribute values that
   reached it, so the gap is actionable without reading the rule table.
3. When several required slots are unmatched, the error reports ALL of them,
   not just the first — one round trip should tell a rule author everything
   that is missing.
4. Refusal leaves NO trace: no ``mrp.bom`` and no ``mrp.bom.line`` records are
   created, and any partial work is rolled back.
5. A refusal caused by an unevaluable expression (see test_parameter_
   expressions) is reported the same way and is likewise atomic.
6. Refusal is a domain error a caller can catch and present, not a bare
   exception.
7. A variant whose required slots ALL match generates normally — refusal must
   not be over-eager.
"""

from odoo.exceptions import UserError
from odoo.tests import tagged

from .builders import RuleSetBuilderMixin
from .common import BomVariantRuleCommon


@tagged("post_install", "-at_install", "mrp_bom_variant_rule")
class TestRequiredSlotRefusal(BomVariantRuleCommon, RuleSetBuilderMixin):
    def _ruleset_missing_large(self):
        """A ruleset whose only vessel rule covers Small, so a Large variant
        reaches the required slot with nothing to match."""
        rule_set = self._rule_set()
        slot = self._slot(rule_set, "Vessel", required=True)
        self._rule(
            slot,
            self._component("Small Vessel"),
            conditions=[(self.attr_size, self.size_small)],
        )
        return rule_set

    def test_unmatched_required_slot_raises(self):
        """Criterion 1."""
        self._ruleset_missing_large()
        variant = self._variant(self.size_large, self.count_single)

        with self.assertRaises(UserError):
            variant._bom_rule_generate()

    def test_error_names_slot_and_attribute_values(self):
        """Criterion 2."""
        self._ruleset_missing_large()
        variant = self._variant(self.size_large, self.count_twin)

        with self.assertRaises(UserError) as caught:
            variant._bom_rule_generate()

        message = str(caught.exception)
        self.assertIn("Vessel", message)
        self.assertIn("Large", message)
        self.assertIn("Twin", message)

    def test_error_reports_every_unmatched_required_slot(self):
        """Criterion 3."""
        rule_set = self._rule_set()
        for name in ("Vessel", "Control Valve", "Media"):
            slot = self._slot(rule_set, name)
            self._rule(
                slot,
                self._component("%s (Small)" % name),
                conditions=[(self.attr_size, self.size_small)],
            )
        variant = self._variant(self.size_large, self.count_single)

        with self.assertRaises(UserError) as caught:
            variant._bom_rule_generate()

        message = str(caught.exception)
        for name in ("Vessel", "Control Valve", "Media"):
            self.assertIn(name, message)

    def test_refusal_creates_no_bom_records(self):
        """Criterion 4."""
        rule_set = self._ruleset_missing_large()
        # A second slot that resolves cleanly, so the refusal happens with
        # usable work already in hand: none of it may be persisted.
        self._rule(
            self._slot(rule_set, "Media", sequence=20),
            self._component("Resin"),
            qty_expr="volume",
        )
        variant = self._variant(self.size_large, self.count_single)
        boms_before = self.env["mrp.bom"].search_count([])
        lines_before = self.env["mrp.bom.line"].search_count([])

        with self.assertRaises(UserError):
            variant._bom_rule_generate()

        self.assertEqual(self.env["mrp.bom"].search_count([]), boms_before)
        self.assertEqual(
            self.env["mrp.bom.line"].search_count([]), lines_before
        )
        self.assertFalse(variant._bom_rule_bom())

    def test_unevaluable_expression_refuses_atomically(self):
        """Criterion 5."""
        rule_set = self._rule_set()
        self._rule(
            self._slot(rule_set, "Vessel", sequence=10),
            self._component("Vessel"),
            qty_expr="1",
        )
        self._rule(
            self._slot(rule_set, "Media", sequence=20),
            self._component("Resin"),
            qty_expr="unknown_param * 2",
        )
        variant = self._variant(self.size_large, self.count_single)
        boms_before = self.env["mrp.bom"].search_count([])

        with self.assertRaises(UserError) as caught:
            variant._bom_rule_generate()

        message = str(caught.exception)
        self.assertIn("Media", message)
        self.assertIn("unknown_param", message)
        self.assertEqual(self.env["mrp.bom"].search_count([]), boms_before)

    def test_refusal_raises_catchable_domain_error(self):
        """Criterion 6."""
        self._ruleset_missing_large()
        variant = self._variant(self.size_large, self.count_single)

        # A caller presenting this to a user must be able to catch it as a
        # domain error rather than having to trap Exception.
        try:
            variant._bom_rule_generate()
        except UserError as err:
            self.assertTrue(str(err).strip())
        else:
            self.fail("generation should have refused")

    def test_fully_matched_variant_generates(self):
        """Criterion 7."""
        rule_set = self._ruleset_missing_large()
        large_vessel = self._component("Large Vessel")
        self._rule(
            rule_set.slot_ids,
            large_vessel,
            sequence=20,
            conditions=[(self.attr_size, self.size_large)],
        )
        variant = self._variant(self.size_large, self.count_single)

        bom = variant._bom_rule_generate()

        self.assertTrue(bom)
        self.assertEqual(bom.bom_line_ids.product_id, large_vessel)
