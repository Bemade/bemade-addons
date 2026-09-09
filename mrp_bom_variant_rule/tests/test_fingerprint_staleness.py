# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html
"""Fingerprinting and stale-BOM reporting.

Acceptance criteria
===================

1. A generated BOM is stamped with a fingerprint of the inputs that produced
   it: the ruleset revision plus the variant's attribute values and the
   parameter values consumed.
2. Regenerating unchanged inputs reproduces the SAME fingerprint. The
   fingerprint is stable across sessions and does not depend on record ids
   ordering or on when it was computed.
3. Editing a rule that the variant's BOM actually used changes the ruleset
   revision, and the BOM is then reported STALE.
4. Editing a rule that this variant's BOM did NOT use does not report it
   stale — precision matters, or the report becomes noise nobody reads.
5. Changing a parameter value on an attribute value the variant uses reports
   its BOM stale.
6. The scheduled action REPORTS stale and unregeneratable BOMs. It must not
   rewrite, archive, or regenerate anything: a cron silently changing what a
   quotation was costed from is exactly the failure this design avoids.
7. The report distinguishes stale-but-regeneratable from would-now-be-refused
   (an unmatched required slot appearing after a rule edit), because the
   second is a rule-table defect needing a human.
8. A hand-built BOM has no fingerprint and never appears in the stale report.
"""

from odoo import Command
from odoo.tests import tagged

from .builders import RuleSetBuilderMixin
from .common import BomVariantRuleCommon


@tagged("post_install", "-at_install", "mrp_bom_variant_rule")
class TestFingerprintStaleness(BomVariantRuleCommon, RuleSetBuilderMixin):
    def setUp(self):
        super().setUp()
        self.vessel = self._component("Vessel")
        self.resin = self._component("Resin")
        self.rule_set = self._rule_set()
        self._populate(self.rule_set, self.attr_size, self.size_small,
                       self.size_large, self.vessel, self.resin)
        self.variant = self._variant(self.size_small, self.count_single)
        self.bom = self.variant._bom_rule_generate()

    def _populate(self, rule_set, attr_size, small, large, vessel, resin):
        """Build the ruleset used by every test here.

        Kept as a parameterised helper so criterion 2 can raise a second,
        structurally identical world from independently created records.
        """
        vessel_slot = self._slot(rule_set, "Vessel", sequence=10)
        self.vessel_rule = self._rule(
            vessel_slot, vessel, qty_expr="volume", sequence=10
        )
        media_slot = self._slot(rule_set, "Media", sequence=20)
        # Only Large variants ever reach this rule, so a Small variant's BOM
        # does not depend on it. Criterion 4 leans on that.
        self.large_rule = self._rule(
            media_slot,
            resin,
            qty_expr="2",
            sequence=10,
            conditions=[(attr_size, large)],
        )
        self.small_rule = self._rule(
            media_slot,
            resin,
            qty_expr="1",
            sequence=20,
            conditions=[(attr_size, small)],
        )

    def _report(self):
        return self.env["mrp.bom"]._bom_rule_stale_report()

    # ------------------------------------------------------------------
    # Criterion 1
    # ------------------------------------------------------------------
    def test_generated_bom_is_fingerprinted(self):
        """Criterion 1."""
        self.assertTrue(self.bom.generated_fingerprint)

        # The variant's attribute values are an input.
        other = self._variant(self.size_large, self.count_twin)
        other_bom = other._bom_rule_generate()
        self.assertNotEqual(
            other_bom.generated_fingerprint, self.bom.generated_fingerprint
        )

        # The ruleset revision is an input.
        before = self.bom.generated_fingerprint
        self.rule_set._bump_revision()
        self.variant._bom_rule_generate(force=True)
        self.assertNotEqual(self.bom.generated_fingerprint, before)

        # A consumed parameter value is an input.
        before = self.bom.generated_fingerprint
        self.size_small.param_ids.filtered(
            lambda p: p.name == "volume"
        ).value = 1.25
        self.variant._bom_rule_generate(force=True)
        self.assertNotEqual(self.bom.generated_fingerprint, before)

    # ------------------------------------------------------------------
    # Criterion 2
    # ------------------------------------------------------------------
    def test_fingerprint_is_stable_for_unchanged_inputs(self):
        """Criterion 2."""
        before = self.bom.generated_fingerprint
        regenerated = self.variant._bom_rule_generate(force=True)
        self.assertEqual(regenerated, self.bom)
        self.assertEqual(regenerated.generated_fingerprint, before)

        # An independently created but structurally identical world must
        # produce the identical fingerprint. That is what "stable across
        # sessions" means in practice: the stamp is a function of the inputs'
        # meaning, never of the database ids that happen to carry them.
        twin_bom = self._parallel_world()
        self.assertEqual(twin_bom.generated_fingerprint, before)

    def _parallel_world(self):
        """Rebuild the whole fixture from scratch and generate its Small BOM."""
        Attribute = self.env["product.attribute"]
        Value = self.env["product.attribute.value"]
        attr_size = Attribute.create({"name": "Size", "create_variant": "dynamic"})
        small = Value.create(
            {
                "name": "Small",
                "attribute_id": attr_size.id,
                "param_ids": [
                    Command.create({"name": "volume", "value": 1.0}),
                    Command.create({"name": "height", "value": 48.0}),
                ],
            }
        )
        large = Value.create(
            {
                "name": "Large",
                "attribute_id": attr_size.id,
                "param_ids": [
                    Command.create({"name": "volume", "value": 1.5}),
                    Command.create({"name": "height", "value": 54.0}),
                ],
            }
        )
        attr_count = Attribute.create(
            {"name": "Count", "create_variant": "dynamic"}
        )
        single = Value.create(
            {
                "name": "Single",
                "attribute_id": attr_count.id,
                "param_ids": [Command.create({"name": "trains", "value": 1.0})],
            }
        )
        twin = Value.create(
            {
                "name": "Twin",
                "attribute_id": attr_count.id,
                "param_ids": [Command.create({"name": "trains", "value": 2.0})],
            }
        )
        template = self.env["product.template"].create(
            {
                "name": "Another Configurable Assembly",
                "type": "consu",
                "attribute_line_ids": [
                    Command.create(
                        {
                            "attribute_id": attr_size.id,
                            "value_ids": [Command.set([small.id, large.id])],
                        }
                    ),
                    Command.create(
                        {
                            "attribute_id": attr_count.id,
                            "value_ids": [Command.set([single.id, twin.id])],
                        }
                    ),
                ],
            }
        )
        rule_set = self._rule_set(name="Other Ruleset", templates=template)
        self._populate(
            rule_set,
            attr_size,
            small,
            large,
            self._component("Vessel"),
            self._component("Resin"),
        )
        # A fingerprint that embedded the revision differently in the two
        # worlds would make the comparison below meaningless, so pin it.
        self.assertEqual(rule_set.revision, self.rule_set.revision)

        ptavs = self.env["product.template.attribute.value"].search(
            [
                ("product_tmpl_id", "=", template.id),
                ("product_attribute_value_id", "in", [small.id, single.id]),
            ]
        )
        variant = template._create_product_variant(ptavs)
        return variant._bom_rule_generate()

    # ------------------------------------------------------------------
    # Criterion 3
    # ------------------------------------------------------------------
    def test_editing_a_used_rule_marks_bom_stale(self):
        """Criterion 3."""
        self.assertNotIn(self.bom, self._report()["stale"])
        revision = self.rule_set.revision

        self.vessel_rule.qty_expr = "volume * 2"

        self.assertGreater(self.rule_set.revision, revision)
        self.assertIn(self.bom, self._report()["stale"])

    # ------------------------------------------------------------------
    # Criterion 4
    # ------------------------------------------------------------------
    def test_editing_an_unused_rule_does_not_mark_bom_stale(self):
        """Criterion 4."""
        revision = self.rule_set.revision

        self.large_rule.qty_expr = "5"

        # The ruleset as a whole did move, which is exactly why a report keyed
        # on the revision alone would be useless.
        self.assertGreater(self.rule_set.revision, revision)
        report = self._report()
        self.assertNotIn(self.bom, report["stale"])
        self.assertNotIn(self.bom, report["refused"])

    # ------------------------------------------------------------------
    # Criterion 5
    # ------------------------------------------------------------------
    def test_changing_a_used_parameter_marks_bom_stale(self):
        """Criterion 5."""
        self.assertNotIn(self.bom, self._report()["stale"])

        self.size_small.param_ids.filtered(
            lambda p: p.name == "volume"
        ).value = 3.0

        self.assertIn(self.bom, self._report()["stale"])

    # ------------------------------------------------------------------
    # Criterion 6
    # ------------------------------------------------------------------
    def test_cron_reports_without_rewriting(self):
        """Criterion 6."""
        self.vessel_rule.qty_expr = "volume * 2"
        self.assertIn(self.bom, self._report()["stale"])

        before_lines = [
            (line.product_id.id, line.product_qty, line.product_uom_id.id)
            for line in self.bom.bom_line_ids
        ]
        before_fingerprint = self.bom.generated_fingerprint
        before_count = self.env["mrp.bom"].search_count([])

        report = self.env["mrp.bom"]._cron_report_stale_boms()

        self.assertIn(self.bom, report["stale"])
        self.bom.invalidate_recordset()
        self.assertTrue(self.bom.active)
        self.assertEqual(
            [
                (line.product_id.id, line.product_qty, line.product_uom_id.id)
                for line in self.bom.bom_line_ids
            ],
            before_lines,
        )
        self.assertEqual(self.bom.generated_fingerprint, before_fingerprint)
        self.assertEqual(self.env["mrp.bom"].search_count([]), before_count)

    # ------------------------------------------------------------------
    # Criterion 7
    # ------------------------------------------------------------------
    def test_report_separates_stale_from_would_be_refused(self):
        """Criterion 7."""
        twin_variant = self._variant(self.size_large, self.count_twin)
        twin_bom = twin_variant._bom_rule_generate()

        # A required slot whose only rule is restricted to Twin: the Twin
        # variant simply gains a line, while the Single variant can no longer
        # be built at all.
        valve = self._component("Valve")
        self._rule(
            self._slot(self.rule_set, "Valve", sequence=30),
            valve,
            qty_expr="trains",
            conditions=[(self.attr_count, self.count_twin)],
        )

        report = self._report()

        self.assertIn(twin_bom, report["stale"])
        self.assertNotIn(twin_bom, report["refused"])
        self.assertIn(self.bom, report["refused"])
        self.assertNotIn(self.bom, report["stale"])
        # The refusal reason has to reach a human, naming the slot at fault.
        self.assertIn("Valve", report["reasons"][self.bom.id])

    # ------------------------------------------------------------------
    # Criterion 8
    # ------------------------------------------------------------------
    def test_hand_built_bom_absent_from_stale_report(self):
        """Criterion 8."""
        plain = self.env["product.product"].create(
            {"name": "Hand Built Assembly", "type": "consu"}
        )
        hand_built = self.env["mrp.bom"].create(
            {
                "product_tmpl_id": plain.product_tmpl_id.id,
                "product_qty": 1.0,
                "bom_line_ids": [
                    Command.create(
                        {"product_id": self.vessel.id, "product_qty": 1.0}
                    )
                ],
            }
        )

        self.assertFalse(hand_built.generated_fingerprint)

        # Even with the ruleset moved out from under everything, a BOM nobody
        # generated is none of the report's business.
        self.vessel_rule.qty_expr = "volume * 2"
        report = self._report()
        self.assertNotIn(hand_built, report["stale"])
        self.assertNotIn(hand_built, report["refused"])
