# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html
"""Use case: one rule, a table of components.

Some slots take a different component for each value of an attribute -- a
pressure vessel per tank size, a distributor per opening. Expressed as fixed
rules that is one rule per component, each carrying the list of values that
select it, and the table a person actually maintains has to be reconstructed
in their head from the conditions. A mapping keeps the table.

ACCEPTANCE CRITERIA
1. A mapped rule contributes the component its table gives for the variant's
   value of the mapped attribute.
2. A value with no row contributes nothing. The slot reports itself unfilled
   rather than falling back to another row, because a plausible substitute is
   the failure this whole engine exists to prevent.
3. When a value has no row, a later rule in the same slot may still match --
   an absent row is no different from a condition that did not hold.
4. Quantity expressions work the same in either mode: the table decides what,
   the expression decides how much.
5. A row may override the unit of measure, for a component whose table entry
   is bought differently from the default.
6. A row keyed on a value of some other attribute is refused at save time. It
   could never match, and a table that looks complete but silently skips a
   value is worse than one that is visibly short.
7. A rule that can name no component at all -- fixed with no product, mapped
   with no attribute -- is refused at save time rather than at generation.
"""
from odoo import Command
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from .builders import RuleSetBuilderMixin
from .common import BomVariantRuleCommon


@tagged("-at_install", "post_install")
class TestMappingRules(BomVariantRuleCommon, RuleSetBuilderMixin):
    def setUp(self):
        super().setUp()
        self.small = self._component("Vessel small")
        self.large = self._component("Vessel large")
        self.rule_set = self._rule_set()
        self.slot = self._slot(self.rule_set, "Vessel")

    def _mapped_rule(self, table, qty_expr="1", sequence=10):
        rule = self.env["mrp.bom.rule"].create(
            {
                "slot_id": self.slot.id,
                "sequence": sequence,
                "selection_mode": "mapped",
                "mapping_attribute_id": self.attr_size.id,
                "qty_expr": qty_expr,
                "mapping_ids": [
                    Command.create(
                        {"attribute_value_id": value.id, "product_id": product.id}
                    )
                    for value, product in table
                ],
            }
        )
        return rule

    def _resolve(self, variant):
        return {
            component: qty
            for _rule, component, qty, _uom in variant._bom_rule_resolve_lines(
                self.rule_set
            )
        }

    def test_table_chooses_the_component(self):
        self._mapped_rule([(self.size_small, self.small), (self.size_large, self.large)])
        self.assertIn(self.small, self._resolve(self._variant(self.size_small, self.count_single)))
        self.assertIn(self.large, self._resolve(self._variant(self.size_large, self.count_single)))

    def test_value_with_no_row_leaves_the_slot_unfilled(self):
        self._mapped_rule([(self.size_small, self.small)])
        with self.assertRaises(UserError) as caught:
            self._variant(self.size_large, self.count_single)._bom_rule_resolve_lines(self.rule_set)
        self.assertIn("Vessel", str(caught.exception))

    def test_a_later_rule_still_gets_its_turn(self):
        """An absent row is not a veto: it is simply this rule declining."""
        self._mapped_rule([(self.size_small, self.small)], sequence=10)
        fallback = self._component("Vessel, made to order")
        self._rule(self.slot, fallback, qty_expr="1", sequence=20)
        self.assertIn(fallback, self._resolve(self._variant(self.size_large, self.count_single)))

    def test_quantity_expression_applies_to_mapped_components(self):
        self._mapped_rule(
            [(self.size_small, self.small), (self.size_large, self.large)],
            qty_expr="trains * 2",
        )
        resolved = self._resolve(self._variant(self.size_large, self.count_twin))
        self.assertAlmostEqual(resolved[self.large], 4.0)

    def test_a_row_may_override_the_unit(self):
        litre = self.env.ref("uom.product_uom_litre", raise_if_not_found=False)
        if not litre:
            self.skipTest("no litre unit on this database")
        rule = self._mapped_rule([(self.size_small, self.small)])
        rule.mapping_ids.product_uom_id = litre
        variant = self._variant(self.size_small, self.count_single)
        uoms = [uom for *_rest, uom in variant._bom_rule_resolve_lines(self.rule_set)]
        self.assertEqual(uoms, [litre])

    def test_row_keyed_on_another_attribute_is_refused(self):
        rule = self._mapped_rule([(self.size_small, self.small)])
        with self.assertRaises(ValidationError):
            self.env["mrp.bom.rule.mapping"].create(
                {
                    "rule_id": rule.id,
                    "attribute_value_id": self.count_twin.id,
                    "product_id": self.large.id,
                }
            )

    def test_a_rule_that_can_name_nothing_is_refused(self):
        with self.assertRaises(ValidationError):
            self.env["mrp.bom.rule"].create(
                {"slot_id": self.slot.id, "selection_mode": "fixed", "qty_expr": "1"}
            )
        with self.assertRaises(ValidationError):
            self.env["mrp.bom.rule"].create(
                {"slot_id": self.slot.id, "selection_mode": "mapped", "qty_expr": "1"}
            )

    def test_a_blank_cell_is_named_not_merely_missed(self):
        """A blank cell is a legitimate state -- there are combinations nobody
        has sold and nobody wants to invent a product for. What must not happen
        is that the blank goes unnamed, leaving someone to open every rule in
        the slot to find out which one declined."""
        self._mapped_rule([(self.size_small, self.small)])
        with self.assertRaises(UserError) as caught:
            self._variant(
                self.size_large, self.count_single
            )._bom_rule_resolve_lines(self.rule_set)
        message = str(caught.exception)
        self.assertIn("Vessel", message)
        self.assertIn(self.attr_size.name, message)
        self.assertIn(self.size_large.name, message)

    def test_a_row_may_answer_with_nothing(self):
        """"Supplies nothing" is an answer and satisfies the slot, where a
        missing row is a question and refuses. The two must not look alike."""
        rule = self._mapped_rule([(self.size_small, self.small)])
        self.env["mrp.bom.rule.mapping"].create(
            {
                "rule_id": rule.id,
                "attribute_value_id": self.size_large.id,
                "supplies_nothing": True,
            }
        )
        resolved = self._resolve(self._variant(self.size_large, self.count_single))
        self.assertEqual(resolved, {}, "the slot should contribute no line")
        # ...and crucially it did not raise: the slot counts as answered.

    def test_a_row_cannot_both_name_a_component_and_supply_nothing(self):
        rule = self._mapped_rule([(self.size_small, self.small)])
        with self.assertRaises(ValidationError):
            self.env["mrp.bom.rule.mapping"].create(
                {
                    "rule_id": rule.id,
                    "attribute_value_id": self.size_large.id,
                    "supplies_nothing": True,
                    "product_id": self.large.id,
                }
            )

    def test_a_row_that_says_nothing_at_all_is_refused(self):
        """Leaving the row out means the question is open; a row present but
        empty says neither, and would quietly satisfy nothing."""
        rule = self._mapped_rule([(self.size_small, self.small)])
        with self.assertRaises(ValidationError):
            self.env["mrp.bom.rule.mapping"].create(
                {"rule_id": rule.id, "attribute_value_id": self.size_large.id}
            )

    def test_a_whole_rule_may_answer_with_nothing(self):
        """For slots that are not mapped -- the flow control has to disappear
        too when the valve is supplied by others, and it keys on tank size."""
        self.env["mrp.bom.rule"].create(
            {
                "slot_id": self.slot.id,
                "sequence": 1,
                "selection_mode": "none",
                "qty_expr": "1",
                "condition_ids": [
                    Command.create(
                        {
                            "attribute_id": self.attr_size.id,
                            "value_ids": [Command.set([self.size_large.id])],
                        }
                    )
                ],
            }
        )
        self._mapped_rule([(self.size_small, self.small)], sequence=10)
        self.assertEqual(
            self._resolve(self._variant(self.size_large, self.count_single)), {}
        )
        self.assertIn(
            self.small, self._resolve(self._variant(self.size_small, self.count_single))
        )
