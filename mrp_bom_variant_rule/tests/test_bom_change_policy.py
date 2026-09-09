# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html
"""How regeneration is allowed to treat a generated BOM that already exists.

Whether a generated bill of materials may be rewritten is a product lifecycle
decision, not a manufacturing one. Odoo freezes an ``mrp.production``'s
``move_raw_ids`` at confirmation, so rewriting the source bill of materials
afterwards cannot change what that order builds; the state of any
manufacturing order is therefore irrelevant to the question. What matters is
whether the business treats a generated bill of materials as a disposable
working document or as a controlled revision.

The choice is a single global setting, ``ir.config_parameter``
``mrp_bom_variant_rule.bom_change_policy``.

Acceptance criteria
===================

1. With no setting stored, the policy is ``overwrite``.
2. Under ``overwrite``, regeneration rewrites the existing generated BOM in
   place: same record, new lines, no predecessor recorded.
3. Under ``overwrite``, no second generated BOM is created and nothing is
   archived.
4. Under ``revision``, regeneration does not modify the existing BOM in place
   — neither its lines nor its quantities.
5. Under ``revision``, regeneration produces a different active BOM and
   retires the original by archiving it, never by deleting it.
6. Under ``revision``, the resulting BOM records its predecessor, so the chain
   of revisions is traceable.
7. Under ``revision``, exactly one ACTIVE generated BOM exists for the variant
   afterwards, and ``_bom_rule_bom()`` returns it. Archived predecessors are
   never returned as "the variant's BOM".
8. Generating a variant's FIRST bill of materials behaves identically under
   both policies: a plain create, with no predecessor and nothing retired.
9. The state of any manufacturing order referencing the BOM has no bearing on
   which path is taken. A confirmed order under ``overwrite`` still gets an
   in-place rewrite, and the order keeps pointing at a readable BOM either
   way.
10. The setting is reachable through ``res.config.settings`` and what is saved
    there is what regeneration obeys.
"""

from odoo.tests import Form, tagged

from .builders import RuleSetBuilderMixin
from .common import BomVariantRuleCommon

POLICY_PARAM = "mrp_bom_variant_rule.bom_change_policy"


@tagged("post_install", "-at_install", "mrp_bom_variant_rule")
class TestBomChangePolicy(BomVariantRuleCommon, RuleSetBuilderMixin):
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

    def _set_policy(self, policy):
        self.env["ir.config_parameter"].sudo().set_param(POLICY_PARAM, policy)

    def _extend_ruleset(self):
        """Add a second slot, so a regeneration has something to change."""
        self.media = self._component("Resin")
        self._rule(
            self._slot(self.rule_set, "Media", sequence=20),
            self.media,
            qty_expr="volume",
        )

    def _all_generated(self):
        return (
            self.env["mrp.bom"]
            .with_context(active_test=False)
            .search(
                [
                    ("product_id", "=", self.variant.id),
                    ("generated_rule_set_id", "!=", False),
                ]
            )
        )

    def _active_generated(self):
        return self.env["mrp.bom"].search(
            [
                ("product_id", "=", self.variant.id),
                ("generated_rule_set_id", "!=", False),
            ]
        )

    def _manufacturing_order(self, bom, confirm):
        form = Form(self.env["mrp.production"])
        form.product_id = self.variant
        mo = form.save()
        self.assertEqual(mo.bom_id, bom)
        if confirm:
            mo.action_confirm()
            self.assertNotEqual(mo.state, "draft")
        return mo

    def test_default_policy_is_overwrite(self):
        """Criterion 1."""
        self.env["ir.config_parameter"].sudo().search(
            [("key", "=", POLICY_PARAM)]
        ).unlink()
        self.assertEqual(
            self.env["product.product"]._bom_rule_change_policy(), "overwrite"
        )

    def test_overwrite_rewrites_in_place(self):
        """Criterion 2."""
        original = self.variant._bom_rule_generate()
        self._set_policy("overwrite")
        self._extend_ruleset()

        regenerated = self.variant._bom_rule_generate(force=True)

        self.assertEqual(regenerated, original)
        self.assertTrue(regenerated.active)
        self.assertFalse(regenerated.generated_predecessor_id)
        self.assertEqual(
            sorted(regenerated.bom_line_ids.mapped("product_id.name")),
            ["Resin", "Vessel"],
        )

    def test_overwrite_creates_nothing_and_archives_nothing(self):
        """Criterion 3."""
        original = self.variant._bom_rule_generate()
        self._set_policy("overwrite")
        self._extend_ruleset()

        self.variant._bom_rule_generate(force=True)

        self.assertEqual(self._all_generated(), original)
        self.assertTrue(original.active)

    def test_revision_does_not_mutate_the_original(self):
        """Criterion 4."""
        original = self.variant._bom_rule_generate()
        self._set_policy("revision")
        self._extend_ruleset()

        self.variant._bom_rule_generate(force=True)

        self.assertEqual(original.bom_line_ids.product_id, self.vessel)
        self.assertEqual(original.bom_line_ids.product_qty, 1.0)

    def test_revision_archives_rather_than_deletes(self):
        """Criterion 5."""
        original = self.variant._bom_rule_generate()
        self._set_policy("revision")
        self._extend_ruleset()

        successor = self.variant._bom_rule_generate(force=True)

        self.assertNotEqual(successor, original)
        self.assertTrue(successor.active)
        self.assertFalse(original.active)
        self.assertTrue(
            self.env["mrp.bom"]
            .with_context(active_test=False)
            .browse(original.id)
            .exists()
        )
        self.assertEqual(
            sorted(successor.bom_line_ids.mapped("product_id.name")),
            ["Resin", "Vessel"],
        )

    def test_revision_records_the_predecessor(self):
        """Criterion 6."""
        original = self.variant._bom_rule_generate()
        self._set_policy("revision")
        self._extend_ruleset()

        successor = self.variant._bom_rule_generate(force=True)

        self.assertEqual(successor.generated_predecessor_id, original)
        self.assertFalse(original.generated_predecessor_id)

    def test_revision_leaves_exactly_one_active_generated_bom(self):
        """Criterion 7."""
        original = self.variant._bom_rule_generate()
        self._set_policy("revision")
        self._extend_ruleset()

        successor = self.variant._bom_rule_generate(force=True)

        self.assertEqual(self._active_generated(), successor)
        self.assertEqual(self.variant._bom_rule_bom(), successor)
        self.assertNotEqual(self.variant._bom_rule_bom(), original)

    def test_first_generation_is_unaffected_by_policy(self):
        """Criterion 8."""
        for policy in ("overwrite", "revision"):
            with self.subTest(policy=policy):
                variant = self._variant(
                    self.size_large,
                    self.count_single
                    if policy == "overwrite"
                    else self.count_twin,
                )
                self._set_policy(policy)

                bom = variant._bom_rule_generate()

                self.assertTrue(bom.active)
                self.assertFalse(bom.generated_predecessor_id)
                self.assertEqual(
                    self.env["mrp.bom"]
                    .with_context(active_test=False)
                    .search_count(
                        [
                            ("product_id", "=", variant.id),
                            ("generated_rule_set_id", "!=", False),
                        ]
                    ),
                    1,
                )

    def test_confirmed_mo_does_not_force_a_revision(self):
        """Criterion 9.

        The premise this replaces was that a confirmed manufacturing order
        made the BOM untouchable. It does not: Odoo froze that order's raw
        moves at confirmation, so the order is unaffected either way.
        """
        original = self.variant._bom_rule_generate()
        mo = self._manufacturing_order(original, confirm=True)
        self._set_policy("overwrite")
        self._extend_ruleset()

        regenerated = self.variant._bom_rule_generate(force=True)

        self.assertEqual(regenerated, original)
        self.assertEqual(mo.bom_id, original)
        self.assertTrue(mo.bom_id.active)

    def test_confirmed_mo_keeps_its_bom_readable_under_revision(self):
        """Criterion 9, the other half."""
        original = self.variant._bom_rule_generate()
        mo = self._manufacturing_order(original, confirm=True)
        self._set_policy("revision")
        self._extend_ruleset()

        self.variant._bom_rule_generate(force=True)

        self.assertEqual(mo.bom_id, original)
        self.assertEqual(mo.bom_id.bom_line_ids.product_id, self.vessel)

    def test_setting_saved_from_config_drives_regeneration(self):
        """Criterion 10."""
        original = self.variant._bom_rule_generate()
        settings = self.env["res.config.settings"].create(
            {"bom_rule_change_policy": "revision"}
        )
        settings.execute()
        self.assertEqual(
            self.env["ir.config_parameter"].sudo().get_param(POLICY_PARAM),
            "revision",
        )
        self._extend_ruleset()

        successor = self.variant._bom_rule_generate(force=True)

        self.assertNotEqual(successor, original)
        self.assertFalse(original.active)
