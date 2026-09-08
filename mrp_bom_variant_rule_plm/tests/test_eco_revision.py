# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html
"""Revisions of a generated BOM go through an engineering change order.

With ``mrp_plm`` installed, the ``revision`` change policy stops meaning "copy
the BOM and archive the old one" and starts meaning what it means everywhere
else in the system: an ``mrp.eco``. The bridge contributes the resolved lines
and lets mrp_plm do the versioning, the diff and the activation.

Acceptance criteria
===================

1. Generating a variant's FIRST bill of materials never creates an ECO, under
   either policy. There is nothing to change.
2. Under the ``overwrite`` policy the bridge is inert: regeneration rewrites
   the BOM in place and no ECO is created, even though mrp_plm is installed.
3. Under ``revision``, regeneration creates one ECO against the existing BOM,
   of type ``bom``, carrying the configured ECO type, and mrp_plm's
   ``action_new_revision`` has run (state ``progress``, ``new_bom_id`` set,
   version bumped, ``previous_bom_id`` pointing at the old BOM).
4. The lines on ``new_bom_id`` are exactly what the rules now resolve to.
5. ``bom_change_ids`` reports the difference, computed by mrp_plm. The bridge
   does not diff anything itself.
6. With auto-apply OFF the ECO is left for a human: the OLD bill of materials
   is still the active one, ``_bom_rule_bom()`` returns it, and the pending
   revision is not returned as the variant's bill of materials.
7. With auto-apply OFF, a quotation costed after the rule change and before
   the approval is costed from the PRE-CHANGE bill of materials. This is the
   most consequential behaviour of the feature.
8. With auto-apply ON, the ECO is applied at once: the new bill of materials
   is active, the old one is archived, ``previous_bom_id`` is set by mrp_plm,
   and the ECO is done.
9. The new bill of materials carries the generation stamps — ruleset,
   fingerprint and predecessor — so it is recognised as the variant's
   generated bill of materials afterwards.
10. Auto-apply defaults to ON, and turning it off through
    ``res.config.settings`` sticks.
11. The ECO type defaults to mrp_plm's "BOM Updates" and can be pointed at
    another existing type through the settings. The module ships none of its
    own.
12. Both settings, and the core policy setting they sit beside, build into
    the Manufacturing settings form.
"""

from odoo.tests import Form, tagged

from odoo.addons.mrp_bom_variant_rule.tests.builders import RuleSetBuilderMixin
from odoo.addons.mrp_bom_variant_rule.tests.common import BomVariantRuleCommon

POLICY_PARAM = "mrp_bom_variant_rule.bom_change_policy"
ECO_TYPE_PARAM = "mrp_bom_variant_rule_plm.eco_type_id"
AUTO_APPLY_PARAM = "mrp_bom_variant_rule_plm.eco_auto_apply"


@tagged("post_install", "-at_install", "mrp_bom_variant_rule_plm")
class TestEcoRevision(BomVariantRuleCommon, RuleSetBuilderMixin):
    def setUp(self):
        super().setUp()
        self.rule_set = self._rule_set()
        self.vessel = self._component("Vessel")
        self._rule(
            self._slot(self.rule_set, "Vessel", sequence=10),
            self.vessel,
            qty_expr="1",
        )
        self.variant = self._variant(self.size_small, self.count_single)
        self._set_param(POLICY_PARAM, "revision")

    def _set_param(self, key, value):
        self.env["ir.config_parameter"].sudo().set_param(key, value)

    def _extend_ruleset(self):
        """Add a second slot, so a regeneration has something to change."""
        self.media = self._component("Resin")
        self._rule(
            self._slot(self.rule_set, "Media", sequence=20),
            self.media,
            qty_expr="volume",
        )

    def _ecos(self):
        return self.env["mrp.eco"].search(
            [("product_tmpl_id", "=", self.template.id)]
        )

    def _lines(self, bom):
        return sorted(
            (line.product_id.name, line.product_qty)
            for line in bom.bom_line_ids
        )

    def test_first_generation_creates_no_eco(self):
        """Criterion 1."""
        for policy in ("revision", "overwrite"):
            with self.subTest(policy=policy):
                self._set_param(POLICY_PARAM, policy)
                variant = self._variant(
                    self.size_large,
                    self.count_single
                    if policy == "revision"
                    else self.count_twin,
                )

                bom = variant._bom_rule_generate()

                self.assertTrue(bom.active)
                self.assertFalse(self._ecos())

    def test_overwrite_policy_creates_no_eco(self):
        """Criterion 2."""
        original = self.variant._bom_rule_generate()
        self._set_param(POLICY_PARAM, "overwrite")
        self._extend_ruleset()

        regenerated = self.variant._bom_rule_generate(force=True)

        self.assertEqual(regenerated, original)
        self.assertTrue(original.active)
        self.assertFalse(self._ecos())

    def test_revision_creates_one_eco_and_takes_a_new_revision(self):
        """Criterion 3."""
        original = self.variant._bom_rule_generate()
        self._set_param(AUTO_APPLY_PARAM, "0")
        self._extend_ruleset()

        self.variant._bom_rule_generate(force=True)

        eco = self._ecos()
        self.assertEqual(len(eco), 1)
        self.assertEqual(eco.type, "bom")
        self.assertEqual(
            eco.type_id, self.env.ref("mrp_plm.ecotype_bom_update")
        )
        self.assertEqual(eco.bom_id, original)
        self.assertEqual(eco.state, "progress")
        self.assertTrue(eco.new_bom_id)
        self.assertNotEqual(eco.new_bom_id, original)
        self.assertEqual(eco.new_bom_id.previous_bom_id, original)
        self.assertEqual(eco.new_bom_id.version, original.version + 1)
        self.assertIn(self.variant.name, eco.name)

    def test_new_revision_lines_match_the_rules(self):
        """Criterion 4."""
        self.variant._bom_rule_generate()
        self._set_param(AUTO_APPLY_PARAM, "0")
        self._extend_ruleset()

        self.variant._bom_rule_generate(force=True)

        # Small carries volume = 1.0, so the Resin line resolves to 1.0.
        self.assertEqual(
            self._lines(self._ecos().new_bom_id),
            [("Resin", 1.0), ("Vessel", 1.0)],
        )

    def test_eco_reports_the_difference(self):
        """Criterion 5."""
        self.variant._bom_rule_generate()
        self._set_param(AUTO_APPLY_PARAM, "0")
        self._extend_ruleset()

        self.variant._bom_rule_generate(force=True)

        eco = self._ecos()
        self.assertEqual(eco.bom_change_ids.product_id, self.media)

    def test_pending_eco_leaves_the_old_bom_active(self):
        """Criterion 6."""
        original = self.variant._bom_rule_generate()
        self._set_param(AUTO_APPLY_PARAM, "0")
        self._extend_ruleset()

        returned = self.variant._bom_rule_generate(force=True)

        self.assertEqual(returned, original)
        self.assertTrue(original.active)
        self.assertFalse(self._ecos().new_bom_id.active)
        self.assertEqual(self.variant._bom_rule_bom(), original)

    def test_quotation_before_approval_uses_the_pre_change_bom(self):
        """Criterion 7.

        The lazy generation path a quotation line takes is
        ``_bom_rule_generate()`` without ``force``. Until somebody approves
        the ECO, that has to keep answering with the components the customer
        was quoted from.
        """
        original = self.variant._bom_rule_generate()
        self._set_param(AUTO_APPLY_PARAM, "0")
        self._extend_ruleset()
        self.variant._bom_rule_generate(force=True)

        costed = self.variant._bom_rule_generate()

        self.assertEqual(costed, original)
        self.assertEqual(self._lines(costed), [("Vessel", 1.0)])

    def test_auto_apply_activates_the_new_bom(self):
        """Criterion 8."""
        original = self.variant._bom_rule_generate()
        self._extend_ruleset()

        successor = self.variant._bom_rule_generate(force=True)

        eco = self._ecos()
        self.assertEqual(successor, eco.new_bom_id)
        self.assertTrue(successor.active)
        self.assertFalse(original.active)
        self.assertEqual(successor.previous_bom_id, original)
        self.assertEqual(eco.state, "done")
        self.assertEqual(self.variant._bom_rule_bom(), successor)
        self.assertEqual(
            self._lines(successor), [("Resin", 1.0), ("Vessel", 1.0)]
        )

    def test_new_bom_carries_the_generation_stamps(self):
        """Criterion 9."""
        original = self.variant._bom_rule_generate()
        stamp = original.generated_fingerprint
        self._extend_ruleset()

        successor = self.variant._bom_rule_generate(force=True)

        self.assertEqual(successor.generated_rule_set_id, self.rule_set)
        self.assertEqual(successor.generated_predecessor_id, original)
        self.assertTrue(successor.generated_fingerprint)
        self.assertNotEqual(successor.generated_fingerprint, stamp)
        self.assertEqual(successor._bom_rule_stale_state()[0], "current")

    def test_auto_apply_defaults_on_and_can_be_turned_off(self):
        """Criterion 10."""
        self.env["ir.config_parameter"].sudo().search(
            [("key", "=", AUTO_APPLY_PARAM)]
        ).unlink()
        self.assertTrue(
            self.env["product.product"]._bom_rule_eco_auto_apply()
        )

        settings = self.env["res.config.settings"].create(
            {"bom_rule_eco_auto_apply": False}
        )
        settings.execute()

        self.assertFalse(
            self.env["product.product"]._bom_rule_eco_auto_apply()
        )
        # And it survives a round trip back through the settings form, which
        # is where an ir.config_parameter boolean defaulting to True usually
        # springs back on.
        self.assertFalse(
            self.env["res.config.settings"]
            .default_get(["bom_rule_eco_auto_apply"])
            .get("bom_rule_eco_auto_apply")
        )

    def test_configured_eco_type_is_used(self):
        """Criterion 11."""
        self.assertEqual(
            self.env["product.product"]._bom_rule_eco_type(),
            self.env.ref("mrp_plm.ecotype_bom_update"),
        )
        other = self.env.ref("mrp_plm.ecotype0")
        settings = self.env["res.config.settings"].create(
            {"bom_rule_eco_type_id": other.id}
        )
        settings.execute()

        self.variant._bom_rule_generate()
        self._extend_ruleset()
        self.variant._bom_rule_generate(force=True)

        self.assertEqual(self._ecos().type_id, other)

    def test_settings_form_builds(self):
        """Criterion 12."""
        with Form(self.env["res.config.settings"]) as form:
            form.bom_rule_change_policy = "revision"
            form.bom_rule_eco_auto_apply = False
            form.bom_rule_eco_type_id = self.env.ref("mrp_plm.ecotype0")
        self.assertEqual(form.record.bom_rule_change_policy, "revision")
