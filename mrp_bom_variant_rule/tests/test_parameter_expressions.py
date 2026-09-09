# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html
"""Named attribute parameters and quantity expressions.

This is the generalisation that keeps the engine domain-agnostic: attribute
VALUES carry named numbers, and rules do arithmetic over them.

Acceptance criteria
===================

1. A ``product.attribute.value`` may declare any number of named numeric
   parameters (e.g. ``volume_ft3 = 1.5``, ``height_in = 54``, ``trains = 2``).
   Parameter names are unique per attribute value.
2. Generating for a variant builds an evaluation context from the parameters
   of ALL of that variant's attribute values, merged. A rule's ``qty_expr`` is
   evaluated against it.
3. Arithmetic over parameters works and produces the expected quantity:
   ``volume_ft3 * 1.2 * trains`` on a (1.5 ft3, 2-train) variant yields 3.6.
4. A constant expression is valid and yields a fixed quantity, so the common
   "one per assembly" case needs no parameters at all.
5. Evaluation is RESTRICTED. Expressions reaching for builtins, imports,
   attribute access, comprehensions, or environment/record access are refused
   at evaluation with a clear error, not executed. A rule that cannot be
   evaluated safely must never silently yield a quantity.
6. An expression referencing a parameter that no attribute value on the
   variant supplies is refused, naming the missing parameter. It must not
   default to zero — a zero-quantity component silently drops out of the cost.
7. If two of a variant's attribute values declare the SAME parameter name with
   different values, generation is refused as ambiguous, naming the parameter
   and the conflicting values.
8. A resulting quantity that is negative, or not a finite number, is refused.
9. A resulting quantity of exactly zero emits NO line rather than a zero-qty
   line, and this is not an error — it is how a rule declines to contribute.
10. The line's UoM comes from the rule, defaulting to the component's own UoM;
    the computed quantity is expressed in that UoM without conversion.
"""

from odoo import Command
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from odoo.tools.misc import mute_logger

from .builders import RuleSetBuilderMixin
from .common import BomVariantRuleCommon


@tagged("post_install", "-at_install", "mrp_bom_variant_rule")
class TestParameterExpressions(BomVariantRuleCommon, RuleSetBuilderMixin):
    def test_attribute_value_declares_named_parameters(self):
        """Criterion 1."""
        self.assertEqual(
            {p.name: p.value for p in self.size_large.param_ids},
            {"volume": 1.5, "height": 54.0},
        )
        self.assertEqual(
            {p.name: p.value for p in self.count_twin.param_ids},
            {"trains": 2.0},
        )

    def test_parameter_name_unique_per_attribute_value(self):
        """Criterion 1."""
        with self.assertRaises(ValidationError):
            self.size_large.write(
                {"param_ids": [Command.create({"name": "volume", "value": 9.0})]}
            )
        # The same name on a *different* value is fine - that is the point.
        self.assertEqual(
            self.size_small.param_ids.filtered(lambda p: p.name == "volume").value,
            1.0,
        )

    def test_context_merges_parameters_of_all_variant_values(self):
        """Criterion 2."""
        variant = self._variant(self.size_large, self.count_twin)
        self.assertEqual(
            variant._bom_rule_param_context(),
            {"volume": 1.5, "height": 54.0, "trains": 2.0},
        )

    def test_arithmetic_over_parameters(self):
        """Criterion 3."""
        rule_set = self._rule_set()
        media = self._component("Resin")
        self._rule(
            self._slot(rule_set, "Media"),
            media,
            qty_expr="volume * 1.2 * trains",
        )

        variant = self._variant(self.size_large, self.count_twin)
        bom = variant._bom_rule_generate()

        self.assertEqual(bom.bom_line_ids.product_id, media)
        self.assertAlmostEqual(bom.bom_line_ids.product_qty, 3.6, places=6)

    def test_constant_expression(self):
        """Criterion 4."""
        rule_set = self._rule_set()
        valve = self._component("Control Valve")
        self._rule(self._slot(rule_set, "Valve"), valve, qty_expr="3")

        variant = self._variant(self.size_small, self.count_single)
        bom = variant._bom_rule_generate()

        self.assertEqual(bom.bom_line_ids.product_qty, 3.0)

    def test_builtin_access_is_refused(self):
        """Criterion 5."""
        rule_set = self._rule_set()
        valve = self._component("Control Valve")
        slot = self._slot(rule_set, "Valve")
        with self.assertRaises(ValidationError):
            self._rule(slot, valve, qty_expr="abs(volume) + len(volume)")

        # Defence in depth: an expression that reached the database by some
        # route other than the form - a data file, an upgrade script - must
        # still be refused when it is evaluated rather than executed.
        rule = self._rule(slot, valve, qty_expr="1")
        self.env.cr.execute(
            "UPDATE mrp_bom_rule SET qty_expr = %s WHERE id = %s",
            ("abs(volume)", rule.id),
        )
        rule.invalidate_recordset(["qty_expr"])

        variant = self._variant(self.size_small, self.count_single)
        with self.assertRaises(UserError):
            variant._bom_rule_generate()
        self.assertFalse(variant._bom_rule_bom())

    def test_attribute_access_is_refused(self):
        """Criterion 5."""
        rule_set = self._rule_set()
        valve = self._component("Control Valve")
        slot = self._slot(rule_set, "Valve")
        for expr in (
            "volume.__class__",
            "[p for p in (1, 2)]",
            "env['res.users']",
        ):
            with self.assertRaises(ValidationError):
                self._rule(slot, valve, qty_expr=expr)

    def test_missing_parameter_is_refused_not_defaulted(self):
        """Criterion 6."""
        rule_set = self._rule_set()
        media = self._component("Resin")
        self._rule(self._slot(rule_set, "Media"), media, qty_expr="widgets * 2")

        variant = self._variant(self.size_small, self.count_single)
        with self.assertRaises(UserError) as caught:
            variant._bom_rule_generate()
        self.assertIn("widgets", str(caught.exception))
        self.assertFalse(variant._bom_rule_bom())

    def test_conflicting_parameter_across_values_is_refused(self):
        """Criterion 7."""
        # Size Large already declares volume = 1.5; make Twin disagree.
        self.count_twin.write(
            {"param_ids": [Command.create({"name": "volume", "value": 9.0})]}
        )
        rule_set = self._rule_set()
        media = self._component("Resin")
        self._rule(self._slot(rule_set, "Media"), media, qty_expr="volume")

        variant = self._variant(self.size_large, self.count_twin)
        with self.assertRaises(UserError) as caught:
            variant._bom_rule_generate()
        message = str(caught.exception)
        self.assertIn("volume", message)
        self.assertIn("1.5", message)
        self.assertIn("9.0", message)

    def test_negative_quantity_is_refused(self):
        """Criterion 8."""
        rule_set = self._rule_set()
        media = self._component("Resin")
        self._rule(self._slot(rule_set, "Media"), media, qty_expr="volume - 100")

        variant = self._variant(self.size_small, self.count_single)
        with self.assertRaises(UserError):
            variant._bom_rule_generate()
        self.assertFalse(variant._bom_rule_bom())

    def test_non_finite_quantity_is_refused(self):
        """Criterion 8."""
        rule_set = self._rule_set()
        media = self._component("Resin")
        slot = self._slot(rule_set, "Media")
        overflow = self._rule(slot, media, qty_expr="volume * 1e308 * 1e308")

        variant = self._variant(self.size_small, self.count_single)
        with self.assertRaises(UserError):
            variant._bom_rule_generate()

        overflow.qty_expr = "volume / (trains - trains)"
        with self.assertRaises(UserError):
            variant._bom_rule_generate()
        self.assertFalse(variant._bom_rule_bom())

    def test_zero_quantity_emits_no_line(self):
        """Criterion 9."""
        rule_set = self._rule_set()
        vessel = self._component("Vessel")
        brine = self._component("Brine Tank")
        self._rule(self._slot(rule_set, "Vessel", sequence=10), vessel, qty_expr="1")
        # A rule declines to contribute by resolving to zero, which is not an
        # error and must not leave a zero-quantity line behind.
        self._rule(
            self._slot(rule_set, "Brine", sequence=20),
            brine,
            qty_expr="trains - trains",
        )

        variant = self._variant(self.size_small, self.count_single)
        bom = variant._bom_rule_generate()

        self.assertEqual(bom.bom_line_ids.product_id, vessel)
        self.assertNotIn(brine, bom.bom_line_ids.product_id)

    def test_line_uom_defaults_to_component_uom(self):
        """Criterion 10."""
        dozen = self.env.ref("uom.product_uom_dozen")
        rule_set = self._rule_set()
        bolts = self._component("Flange Bolts", uom=dozen)
        self._rule(self._slot(rule_set, "Fasteners"), bolts, qty_expr="trains")

        variant = self._variant(self.size_small, self.count_twin)
        line = variant._bom_rule_generate().bom_line_ids

        self.assertEqual(line.product_uom_id, dozen)
        # Two dozen, not twenty-four units: the expression is already
        # expressed in the line's unit of measure.
        self.assertEqual(line.product_qty, 2.0)
