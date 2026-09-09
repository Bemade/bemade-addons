# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html
"""Lazy, on-demand generation and idempotency.

Acceptance criteria
===================

1. Creating a variant of a template that has a ruleset generates NOTHING. With
   dynamic attributes any configurator interaction creates variants; eager
   generation would produce thousands of BOMs.
2. Generation happens only when explicitly requested — the public entry point
   on the variant, or the regenerate control on the product form.
3. Generation is idempotent: requesting it twice for an unchanged variant and
   ruleset returns the SAME BOM and creates no duplicate. Durpro already has
   softener products carrying two active BOMs; the engine must not add more.
4. The generated BOM has ``product_id`` set to the specific VARIANT, not left
   template-wide, so it cannot bleed onto sibling configurations.
5. The generated BOM records which ruleset produced it, distinguishing it from
   a hand-built BOM. Hand-built BOMs are never adopted, overwritten, or
   counted as generated.
6. If a variant already has a hand-built BOM, generation refuses by default
   rather than competing with it, and says so. A human's BOM outranks a rule.
7. Explicit regeneration after a ruleset change replaces the generated BOM
   (subject to the supersede rules in test_supersede_locked_bom) and leaves
   exactly one active generated BOM for the variant.
8. Generation for a variant whose template has NO ruleset is a no-op returning
   nothing, not an error.
"""

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests import tagged

from .builders import RuleSetBuilderMixin
from .common import BomVariantRuleCommon


@tagged("post_install", "-at_install", "mrp_bom_variant_rule")
class TestLazyGeneration(BomVariantRuleCommon, RuleSetBuilderMixin):
    def _simple_rule_set(self, qty_expr="1"):
        rule_set = self._rule_set()
        self.vessel = self._component("Vessel")
        self._rule(self._slot(rule_set, "Vessel"), self.vessel, qty_expr=qty_expr)
        return rule_set

    def _hand_built_bom(self, variant):
        return self.env["mrp.bom"].create(
            {
                "product_tmpl_id": variant.product_tmpl_id.id,
                "product_id": variant.id,
                "product_qty": 1.0,
                "bom_line_ids": [
                    Command.create(
                        {
                            "product_id": self._component("Hand Picked").id,
                            "product_qty": 7.0,
                        }
                    )
                ],
            }
        )

    def test_variant_creation_generates_nothing(self):
        """Criterion 1."""
        self._simple_rule_set()
        before = self.env["mrp.bom"].search_count([])

        variant = self._variant(self.size_small, self.count_single)

        self.assertEqual(self.env["mrp.bom"].search_count([]), before)
        self.assertFalse(variant._bom_rule_bom())

    def test_explicit_request_generates(self):
        """Criterion 2."""
        self._simple_rule_set()
        variant = self._variant(self.size_small, self.count_single)

        bom = variant._bom_rule_generate()

        self.assertTrue(bom)
        self.assertEqual(variant._bom_rule_bom(), bom)

        # The product form's regenerate control is the same operation, and
        # hands the caller back the bill of materials it produced.
        action = variant.action_bom_rule_regenerate()
        self.assertEqual(action["res_model"], "mrp.bom")
        self.assertEqual(action["res_id"], variant._bom_rule_bom().id)

    def test_second_request_returns_same_bom(self):
        """Criterion 3."""
        self._simple_rule_set()
        variant = self._variant(self.size_small, self.count_single)

        first = variant._bom_rule_generate()
        second = variant._bom_rule_generate()

        self.assertEqual(first, second)

    def test_no_duplicate_active_bom_is_created(self):
        """Criterion 3."""
        self._simple_rule_set()
        variant = self._variant(self.size_small, self.count_single)

        variant._bom_rule_generate()
        variant._bom_rule_generate()

        self.assertEqual(
            self.env["mrp.bom"].search_count([("product_id", "=", variant.id)]),
            1,
        )

    def test_generated_bom_is_variant_scoped(self):
        """Criterion 4."""
        self._simple_rule_set()
        variant = self._variant(self.size_small, self.count_single)
        sibling = self._variant(self.size_large, self.count_twin)

        bom = variant._bom_rule_generate()

        self.assertEqual(bom.product_id, variant)
        self.assertEqual(bom.product_tmpl_id, self.template)
        # A template-wide bill of materials would answer for the sibling too.
        self.assertFalse(sibling._bom_rule_bom())

    def test_generated_bom_records_its_ruleset(self):
        """Criterion 5."""
        rule_set = self._simple_rule_set()
        variant = self._variant(self.size_small, self.count_single)

        bom = variant._bom_rule_generate()

        self.assertEqual(bom.generated_rule_set_id, rule_set)

    def test_hand_built_bom_is_not_adopted(self):
        """Criterion 5."""
        self._simple_rule_set()
        variant = self._variant(self.size_small, self.count_single)
        hand_built = self._hand_built_bom(variant)

        self.assertFalse(hand_built.generated_rule_set_id)
        self.assertFalse(variant._bom_rule_bom())

    def test_generation_refuses_over_hand_built_bom(self):
        """Criterion 6."""
        self._simple_rule_set()
        variant = self._variant(self.size_small, self.count_single)
        hand_built = self._hand_built_bom(variant)

        with self.assertRaises(UserError) as caught:
            variant._bom_rule_generate()

        self.assertIn("bill of materials", str(caught.exception).lower())
        self.assertTrue(hand_built.active)
        self.assertEqual(hand_built.bom_line_ids.product_qty, 7.0)
        self.assertEqual(
            self.env["mrp.bom"].search_count([("product_id", "=", variant.id)]),
            1,
        )

    def test_regeneration_leaves_one_active_generated_bom(self):
        """Criterion 7."""
        rule_set = self._simple_rule_set()
        variant = self._variant(self.size_small, self.count_single)
        variant._bom_rule_generate()

        media = self._component("Resin")
        self._rule(
            self._slot(rule_set, "Media", sequence=20), media, qty_expr="volume"
        )
        regenerated = variant._bom_rule_generate(force=True)

        self.assertEqual(
            self.env["mrp.bom"].search_count(
                [
                    ("product_id", "=", variant.id),
                    ("generated_rule_set_id", "!=", False),
                ]
            ),
            1,
        )
        self.assertEqual(variant._bom_rule_bom(), regenerated)
        self.assertEqual(
            sorted(regenerated.bom_line_ids.mapped("product_id.name")),
            ["Resin", "Vessel"],
        )

    def test_template_without_ruleset_is_noop(self):
        """Criterion 8."""
        variant = self._variant(self.size_small, self.count_single)

        result = variant._bom_rule_generate()

        self.assertFalse(result)
        self.assertEqual(result._name, "mrp.bom")
        self.assertFalse(variant._bom_rule_bom())
