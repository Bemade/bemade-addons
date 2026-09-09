# Copyright 2026 Bemade Inc.
# License LGPL-3 - See https://www.gnu.org/licenses/lgpl-3.0.html
"""Quotation-driven generation.

Acceptance criteria
===================

1. Setting a configured variant on a sale order line generates that variant's
   BOM if the ruleset can produce one, so the line can be costed and priced
   from it.
2. Generation on the line is idempotent: re-triggering the onchange, or adding
   the same variant on a second line, reuses the existing BOM.
3. The line surfaces the BOM's state — generated, superseded or refused —
   so the person quoting sees what stands behind the number BEFORE the
   quotation goes out. How trustworthy the component prices underneath it
   are is a SEPARATE axis, surfaced as its own field: a superseded bill of
   materials priced firmly and a current one priced from stale inputs are
   not points on one scale, and forcing them into a single selection would
   make one of them invisible.
4. A refusal (unmatched required slot) does not block editing the quotation.
   The line is still usable and the reason is visible; sales is not stuck
   because the rule table has a hole.
5. A regenerate control on the line re-runs generation after a ruleset
   correction, without leaving the quotation.
6. Generation is NOT hooked into pricelist evaluation. Computing a price in a
   read path — a report, a portal page, a scheduled recomputation — creates no
   records. This is the criterion that keeps the trigger tied to a person
   deliberately configuring something.
7. Confirming the order does not regenerate: what was quoted is what is
   ordered.
8. A line carrying a non-configured product, or a product whose template has
   no ruleset, behaves exactly as stock Odoo does.
9. The module auto-installs whenever both of its dependencies are present.
   It is a bridge rather than pure glue — it adds sales-side behaviour of
   its own — but it must not reimplement anything the engine already
   publishes, in particular the cost-confidence assessment, which it only
   relays.
"""

from odoo import Command
from odoo.tests import Form, tagged

from odoo.addons.mrp_bom_variant_rule.tests.builders import RuleSetBuilderMixin
from odoo.addons.mrp_bom_variant_rule.tests.common import BomVariantRuleCommon


@tagged("post_install", "-at_install", "mrp_bom_variant_rule_sale")
class TestSaleLineGeneration(BomVariantRuleCommon, RuleSetBuilderMixin):
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

    def _quotation(self, product=None):
        """Build a quotation the way a salesperson does, through the form."""
        form = Form(self.env["sale.order"])
        form.partner_id = self.partner
        if product is not None:
            with form.order_line.new() as line:
                line.product_id = product
        return form.save()

    def _generated_bom_count(self, variant=None):
        return (
            self.env["mrp.bom"]
            .with_context(active_test=False)
            .search_count(
                [
                    ("product_id", "=", (variant or self.variant).id),
                    ("generated_rule_set_id", "!=", False),
                ]
            )
        )

    def test_setting_variant_on_line_generates_bom(self):
        """Criterion 1."""
        self.assertFalse(self.variant._bom_rule_bom())

        order = self._quotation(self.variant)

        bom = self.variant._bom_rule_bom()
        self.assertTrue(bom)
        self.assertEqual(bom.generated_rule_set_id, self.rule_set)
        self.assertEqual(order.order_line.bom_rule_bom_id, bom)
        self.assertEqual(order.order_line.bom_rule_state, "generated")

    def test_repeated_trigger_reuses_existing_bom(self):
        """Criterion 2."""
        order = self._quotation(self.variant)
        line = order.order_line
        first = line.bom_rule_bom_id
        self.assertTrue(first)

        # Setting the same product again is what an indecisive salesperson
        # does; it must not produce a second bill of materials.
        line.write({"product_id": self.variant.id})

        self.assertEqual(line.bom_rule_bom_id, first)
        self.assertEqual(self._generated_bom_count(), 1)

    def test_second_line_same_variant_reuses_bom(self):
        """Criterion 2."""
        order = self._quotation(self.variant)
        first = order.order_line.bom_rule_bom_id

        second_order = self._quotation(self.variant)

        self.assertEqual(second_order.order_line.bom_rule_bom_id, first)
        self.assertEqual(self._generated_bom_count(), 1)

    def _unmatched_required_slot(self):
        """Leave a hole in the rule table for the variant under test.

        The slot is required and its only rule is conditioned on the other
        size, so generation for the small variant must refuse.
        """
        self.media_slot = self._slot(self.rule_set, "Media", sequence=20)
        self._rule(
            self.media_slot,
            self._component("Large Resin"),
            qty_expr="volume",
            conditions=[(self.attr_size, self.size_large)],
        )
        return self.media_slot

    def _require_revisions(self):
        """Make regeneration produce a new bill of materials rather than
        rewrite the existing one.

        Whether a generated bill of materials may be overwritten is a product
        lifecycle policy, not a consequence of any manufacturing order: Odoo
        freezes an order's components when it is confirmed, so rewriting the
        bill of materials afterwards cannot change what gets built.
        """
        self.env["ir.config_parameter"].sudo().set_param(
            "mrp_bom_variant_rule.bom_change_policy", "revision"
        )

    def test_line_surfaces_bom_state(self):
        """Criterion 3."""
        order = self._quotation(self.variant)
        line = order.order_line
        self.assertEqual(line.bom_rule_state, "generated")
        quoted = line.bom_rule_bom_id

        self._require_revisions()
        self._rule(
            self._slot(self.rule_set, "Media", sequence=20),
            self._component("Resin"),
            qty_expr="volume",
        )
        self.variant.action_bom_rule_regenerate()

        # The line still points at what it was costed from, and says that it
        # has since been replaced.
        self.assertFalse(quoted.active)
        self.assertEqual(line.bom_rule_bom_id, quoted)
        self.assertEqual(line.bom_rule_state, "superseded")

    def test_refusal_does_not_block_quotation_editing(self):
        """Criterion 4."""
        self._unmatched_required_slot()

        order = self._quotation(self.variant)
        line = order.order_line

        self.assertFalse(line.bom_rule_bom_id)
        self.assertEqual(line.bom_rule_state, "refused")
        self.assertIn("Media", line.bom_rule_message)

        # The quotation stays a working document.
        line.product_uom_qty = 3.0
        line.price_unit = 250.0
        self.assertEqual(line.product_uom_qty, 3.0)
        self.assertEqual(order.amount_untaxed, 750.0)

    def test_regenerate_control_on_line(self):
        """Criterion 5."""
        self._unmatched_required_slot()
        order = self._quotation(self.variant)
        line = order.order_line
        self.assertEqual(line.bom_rule_state, "refused")

        self._rule(
            self.media_slot,
            self._component("Resin"),
            qty_expr="volume",
            sequence=20,
        )
        result = line.action_bom_rule_regenerate()

        # Nothing navigates away: the salesperson stays on the quotation.
        self.assertFalse(result)
        self.assertEqual(line.bom_rule_state, "generated")
        self.assertFalse(line.bom_rule_message)
        self.assertEqual(line.bom_rule_bom_id, self.variant._bom_rule_bom())
        self.assertEqual(order.state, "draft")

        # The control is actually reachable from the order form.
        arch = self.env["sale.order"].get_view()["arch"]
        self.assertIn("action_bom_rule_regenerate", arch)

    def _all_bom_count(self):
        return self.env["mrp.bom"].with_context(active_test=False).search_count([])

    def test_pricelist_evaluation_creates_no_records(self):
        """Criterion 6."""
        order = self._quotation(self.variant)
        # A sibling configuration nothing has configured on a line yet: if
        # pricing generated, this is the variant it would generate for.
        sibling = self._variant(self.size_large, self.count_twin)
        pricelist = self.env["product.pricelist"].create(
            {"name": "Test Pricelist", "currency_id": self.currency.id}
        )
        before = self._all_bom_count()

        pricelist._get_product_price(sibling, 1.0)
        pricelist._get_product_price(self.variant, 5.0)
        # The order-level repricing a currency or pricelist change triggers,
        # and which a scheduled recomputation runs the same way.
        order.pricelist_id = pricelist
        order._recompute_prices()

        self.assertEqual(self._all_bom_count(), before)
        self.assertFalse(sibling._bom_rule_bom())

    def test_report_render_creates_no_records(self):
        """Criterion 6."""
        # The line must be one that generation WOULD produce something for,
        # or the assertion cannot tell a read path from a write path: start
        # from a refusal and correct the rule table without regenerating.
        self._unmatched_required_slot()
        order = self._quotation(self.variant)
        self.assertFalse(order.order_line.bom_rule_bom_id)
        self._rule(
            self.media_slot,
            self._component("Resin"),
            qty_expr="volume",
            sequence=20,
        )
        before = self._all_bom_count()

        # A report renders in its own transaction against cold records, so
        # drop the cache to make the render actually read from the database.
        self.env.invalidate_all()
        # HTML rather than PDF: the rendering path is the same and wkhtmltopdf
        # deadlocks inside a test transaction.
        self.env["ir.actions.report"]._render_qweb_html(
            "sale.report_saleorder", order.ids
        )

        self.assertEqual(self._all_bom_count(), before)
        self.assertFalse(self.variant._bom_rule_bom())

    def test_order_confirmation_does_not_regenerate(self):
        """Criterion 7."""
        order = self._quotation(self.variant)
        line = order.order_line
        quoted = line.bom_rule_bom_id
        # The rule table moves on after the quotation was priced.
        self._rule(
            self._slot(self.rule_set, "Media", sequence=20),
            self._component("Resin"),
            qty_expr="volume",
        )
        before = self._generated_bom_count()

        order.action_confirm()

        self.assertEqual(order.state, "sale")
        self.assertEqual(line.bom_rule_bom_id, quoted)
        self.assertEqual(line.bom_rule_state, "generated")
        self.assertEqual(self._generated_bom_count(), before)
        self.assertEqual(quoted.bom_line_ids.product_id, self.vessel)

    def test_non_configured_product_behaves_as_stock(self):
        """Criterion 8."""
        plain = self._component("Plain Widget")
        before = self.env["mrp.bom"].search_count([])

        order = self._quotation(plain)
        line = order.order_line

        self.assertEqual(line.product_id, plain)
        self.assertEqual(line.product_uom_qty, 1.0)
        self.assertEqual(self.env["mrp.bom"].search_count([]), before)
        self.assertFalse(line.bom_rule_bom_id)
        self.assertEqual(line.bom_rule_state, "none")


@tagged("post_install", "-at_install", "mrp_bom_variant_rule_sale")
class TestSaleLineGenerationAccess(TestSaleLineGeneration):
    """The same behaviour, exercised as a salesperson rather than as root.

    Acceptance criteria
    ===================

    11. A user with sales rights but NO manufacturing rights can configure a
        line and have its bill of materials generated. Generation is an
        internal consequence of quoting, not an action the salesperson is
        performing on the manufacturing model, so it must not require them to
        hold create rights on ``mrp.bom``.
    12. Reading a quotation line's bill-of-materials state does not raise for
        that same user. A list of quotation lines must render for people who
        cannot read ``mrp.bom`` at all.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.salesperson = cls.env["res.users"].create(
            {
                "name": "Sales Only",
                "login": "bom_rule_sales_only",
                "groups_id": [
                    Command.set(
                        [
                            cls.env.ref("base.group_user").id,
                            cls.env.ref("sales_team.group_sale_salesman").id,
                        ]
                    )
                ],
            }
        )

    def test_salesperson_without_mrp_rights_can_generate(self):
        """Criterion 11."""
        variant = self._variant(self.size_large, self.count_twin)
        order = self.env["sale.order"].create(
            {"partner_id": self.partner.id, "user_id": self.salesperson.id}
        )
        line = (
            self.env["sale.order.line"]
            .with_user(self.salesperson)
            .create(
                {
                    "order_id": order.id,
                    "product_id": variant.id,
                    "product_uom_qty": 1.0,
                }
            )
        )
        self.assertEqual(line.bom_rule_state, "generated")
        self.assertTrue(line.bom_rule_bom_id)

    def test_salesperson_without_mrp_rights_can_read_state(self):
        """Criterion 12."""
        variant = self._variant(self.size_large, self.count_twin)
        order = self.env["sale.order"].create(
            {"partner_id": self.partner.id, "user_id": self.salesperson.id}
        )
        line = self.env["sale.order.line"].create(
            {
                "order_id": order.id,
                "product_id": variant.id,
                "product_uom_qty": 1.0,
            }
        )
        self.assertEqual(line.bom_rule_state, "generated")
        # invalidate_recordset() would clear only the line; the bill of
        # materials read during setup would stay cached and the access check
        # this test exists for would never run.
        self.env.invalidate_all()
        as_sales = line.with_user(self.salesperson)
        self.assertEqual(as_sales.bom_rule_state, "generated")


@tagged("post_install", "-at_install", "mrp_bom_variant_rule_sale")
class TestSaleLineCostConfidence(TestSaleLineGeneration):
    """Cost confidence relayed onto the quotation line.

    Acceptance criteria
    ===================

    13. The line exposes the cost confidence of the bill of materials it was
        costed from, relayed from the engine rather than recomputed here.
    14. Confidence is a separate axis from the line's state: a line whose
        bill of materials is Estimated still reports its state accurately,
        and a line with no bill of materials reports no confidence at all.
    """

    def test_line_relays_cost_confidence(self):
        """Criterion 13."""
        variant = self._variant(self.size_large, self.count_twin)
        order = self.env["sale.order"].create({"partner_id": self.partner.id})
        line = self.env["sale.order.line"].create(
            {
                "order_id": order.id,
                "product_id": variant.id,
                "product_uom_qty": 1.0,
            }
        )
        self.assertTrue(line.bom_rule_bom_id)
        self.assertEqual(
            line.bom_rule_cost_confidence,
            line.bom_rule_bom_id.cost_confidence,
        )
        # The fixture's components carry no vendor prices at all, so the
        # engine must be reporting the cost basis as Estimated, not Firm.
        self.assertEqual(line.bom_rule_cost_confidence, "estimated")

    def test_confidence_is_independent_of_state(self):
        """Criterion 14."""
        variant = self._variant(self.size_large, self.count_twin)
        order = self.env["sale.order"].create({"partner_id": self.partner.id})
        line = self.env["sale.order.line"].create(
            {
                "order_id": order.id,
                "product_id": variant.id,
                "product_uom_qty": 1.0,
            }
        )
        # Degraded prices say nothing about whether the bill of materials is
        # the current one; the state must remain accurate alongside it.
        self.assertEqual(line.bom_rule_cost_confidence, "estimated")
        self.assertEqual(line.bom_rule_state, "generated")

        bare = self.env["sale.order.line"].create(
            {
                "order_id": order.id,
                "product_id": self._component("Unruled").id,
                "product_uom_qty": 1.0,
            }
        )
        self.assertEqual(bare.bom_rule_state, "none")
        self.assertFalse(bare.bom_rule_cost_confidence)
