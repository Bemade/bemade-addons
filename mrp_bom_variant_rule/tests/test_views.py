# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html
"""The authoring UI actually builds and can be filled in.

Acceptance criteria
===================

1. A ruleset can be authored end to end through its form: name, bound
   templates, a slot, a rule inside that slot, and a condition inside that
   rule, all in one editing session. This is the module's whole premise — a
   product expert maintains the table — so a view that loads but cannot be
   filled in is a failure, not a cosmetic problem.
2. An attribute value's named parameters can be entered through the value
   form, since a quantity expression is meaningless without them.
3. The generated-BOM fields render on the stock bill-of-materials form, and
   the regeneration control is present on the variant form.
4. Every action and menu the module declares resolves, and each action points
   at the model it claims to.
"""

from odoo.tests import Form, tagged

from .builders import RuleSetBuilderMixin
from .common import BomVariantRuleCommon


@tagged("post_install", "-at_install", "mrp_bom_variant_rule")
class TestViews(BomVariantRuleCommon, RuleSetBuilderMixin):
    def test_rule_set_form_authors_a_whole_rule_table(self):
        """Slots, rules and conditions are all reachable from the ruleset
        form without dropping to the shell."""
        component = self._component("Vessel 1500L")
        form = Form(
            self.env["mrp.bom.rule.set"],
            view="mrp_bom_variant_rule.view_mrp_bom_rule_set_form",
        )
        form.name = "Filtration skid"
        form.product_tmpl_ids.add(self.template)
        with form.slot_ids.new() as slot:
            slot.name = "Vessel"
            slot.required = True
        rule_set = form.save()
        slot = rule_set.slot_ids

        # The rules page is a second pass, because a rule has to name the slot
        # it competes for and a slot only exists once saved.
        form = Form(
            rule_set, view="mrp_bom_variant_rule.view_mrp_bom_rule_set_form"
        )
        with form.rule_ids.new() as rule:
            rule.slot_id = slot
            rule.product_id = component
            rule.qty_expr = "volume * trains"
            with rule.condition_ids.new() as condition:
                condition.attribute_id = self.attr_size
                condition.value_ids.add(self.size_large)
        form.save()

        self.assertEqual(rule_set.slot_ids.name, "Vessel")
        self.assertEqual(rule_set.rule_ids.product_id, component)
        self.assertEqual(rule_set.rule_ids.qty_expr, "volume * trains")
        self.assertEqual(
            rule_set.rule_ids.condition_ids.value_ids, self.size_large
        )
        # The related rule_set_id has to have followed the slot, otherwise the
        # Rules page would show an empty list for a ruleset that has rules.
        self.assertEqual(rule_set.rule_ids.rule_set_id, rule_set)

    def test_rule_set_form_edits_an_existing_ruleset(self):
        """Reopening a saved ruleset and adding a second rule works, which is
        the ordinary case: rule tables grow rather than being written once."""
        rule_set = self._rule_set()
        slot = self._slot(rule_set, "Vessel")
        self._rule(slot, self._component("Vessel Small"), qty_expr="1")
        fallback = self._component("Vessel Default")

        form = Form(
            rule_set, view="mrp_bom_variant_rule.view_mrp_bom_rule_set_form"
        )
        with form.rule_ids.new() as rule:
            rule.slot_id = slot
            rule.product_id = fallback
            rule.qty_expr = "1"
            rule.sequence = 99
        form.save()

        ordered = rule_set.rule_ids.sorted(lambda r: (r.sequence, r.id))
        self.assertEqual(ordered[-1].product_id, fallback)
        # A conditionless rule is the one that shadows everything after it, so
        # the form has to say so rather than showing an empty cell.
        self.assertIn("catch-all", ordered[-1].condition_summary)

    def test_rule_standalone_form(self):
        """The cross-ruleset rule form still requires a slot, and can carry a
        condition of its own."""
        rule_set = self._rule_set()
        slot = self._slot(rule_set, "Pump")
        component = self._component("Pump 2HP")

        form = Form(
            self.env["mrp.bom.rule"],
            view="mrp_bom_variant_rule.view_mrp_bom_rule_form",
        )
        form.slot_id = slot
        form.product_id = component
        form.qty_expr = "trains"
        with form.condition_ids.new() as condition:
            condition.attribute_id = self.attr_count
            condition.value_ids.add(self.count_twin)
        rule = form.save()

        self.assertEqual(rule.rule_set_id, rule_set)
        self.assertEqual(rule.condition_summary, "Count: Twin")

    def test_attribute_value_param_form(self):
        """Parameters are enterable where the values live."""
        form = Form(
            self.env["product.attribute.value"],
            view="mrp_bom_variant_rule.view_product_attribute_value_form",
        )
        form.name = "Extra Large"
        form.attribute_id = self.attr_size
        with form.param_ids.new() as param:
            param.name = "volume"
            param.value = 2.5
        value = form.save()

        self.assertEqual(value.param_ids.name, "volume")
        self.assertIn("volume", value.param_summary)

    def test_attribute_form_reaches_the_parameters(self):
        """The button on the attribute form opens the value that carries the
        parameters, since that is the only route an author will find."""
        action = self.size_large.action_bom_rule_open_params()
        self.assertEqual(action["res_model"], "product.attribute.value")
        self.assertEqual(action["res_id"], self.size_large.id)
        self.assertEqual(
            action["views"][0][0],
            self.env.ref(
                "mrp_bom_variant_rule.view_product_attribute_value_form"
            ).id,
        )

    def test_generated_bom_form_renders(self):
        """The stock BOM form builds with the generated fields on it."""
        rule_set = self._rule_set()
        slot = self._slot(rule_set, "Vessel")
        self._rule(slot, self._component("Vessel"), qty_expr="volume")
        variant = self._variant(self.size_large, self.count_single)
        bom = variant._bom_rule_generate()

        form = Form(bom, view="mrp.mrp_bom_form_view")
        self.assertEqual(form.generated_rule_set_id, rule_set)
        self.assertTrue(form.cost_confidence)

    def test_variant_form_carries_the_regenerate_control(self):
        """The control is on the variant form and knows when it applies."""
        rule_set = self._rule_set()
        variant = self._variant(self.size_small, self.count_single)
        self.assertEqual(variant.bom_rule_set_id, rule_set)

        unrelated = self.env["product.product"].create(
            {"name": "Plain Widget", "type": "consu"}
        )
        self.assertFalse(unrelated.bom_rule_set_id)

        # Both variant forms, not just the normal one. A variant opened from
        # Product Variants uses the normal form; one opened from a template's
        # Variants button uses the easy-edit form, which is a base view rather
        # than an inheritor of the first. This test used to check only the
        # normal form, and so passed while the button was missing from the
        # route most people actually take -- found by hand on staging.
        for xmlid in (
            "product.product_normal_form_view",
            "product.product_variant_easy_edit_view",
        ):
            arch = self.env["product.product"].get_view(
                self.env.ref(xmlid).id, "form"
            )["arch"]
            self.assertIn(
                "action_bom_rule_regenerate",
                arch,
                "the regenerate button is missing from %s" % xmlid,
            )

    def test_actions_and_menus_resolve(self):
        expected = {
            "action_mrp_bom_rule_set": "mrp.bom.rule.set",
            "action_mrp_bom_rule": "mrp.bom.rule",
            "action_product_attribute_value_param": "product.attribute.value",
        }
        for xml_id, model in expected.items():
            action = self.env.ref("mrp_bom_variant_rule.%s" % xml_id)
            self.assertEqual(action.res_model, model, xml_id)

        for xml_id in (
            "menu_mrp_bom_rule_set",
            "menu_mrp_bom_rule",
            "menu_product_attribute_value_param",
        ):
            menu = self.env.ref("mrp_bom_variant_rule.%s" % xml_id)
            self.assertTrue(menu.action, xml_id)
            # Rule authoring is a manager's job: a shop-floor user who can see
            # the menu would find a list they cannot act on.
            self.assertIn(
                self.env.ref("mrp.group_mrp_manager"), menu.groups_id, xml_id
            )
