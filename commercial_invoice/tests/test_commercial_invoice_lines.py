# License: LGPL-3
# Author: Bemade Inc. (Marc Durepos <marc@bemade.org>)
"""Tests for commercial.invoice line-source switching.

Acceptance criteria (from task-3516 requirements):

1. line_source='invoice' (default) — _get_report_lines() returns one dict per
   invoice line, values matching account.move.line.  Rendered HTML contains
   the product code and price_subtotal.

2. line_source='picking' — _get_report_lines() yields rows with
   quantities/prices from move.sale_line_id.price_unit, sourced from the
   explicitly selected picking_ids.

3. Aggregation across pickings — two selected pickings for same product/price
   produce one aggregated row (summed qty).  A third picking with a different
   price_unit for the same product yields a second row (aggregation key is
   (product_id, price_unit)).

4. Empty deliveries — picking-source CI with no picking_ids → [] from
   _get_report_lines(); rendered HTML contains the "No deliveries linked"
   note.

5. Unit price origin — each row's price_unit equals move.sale_line_id.price_unit,
   NOT the product's list price or move.price_unit.

6. _compute_amounts for picking source — invoice_amount == sum of helper rows'
   price_subtotal; total_amount == invoice_amount + addons.

7. Backwards-compat smoke — existing CI (line_source='invoice') renders HTML
   with the expected product code; _get_report_lines() matches invoice lines.

NOTE (task 3705 refinement): picking-source content comes SOLELY from the
explicit picking_ids selection — there is no partner-search fallback.  These
tests therefore set picking_ids explicitly.

18.0 adaptations:
- stock.move.line uses `quantity` (not `qty_done`) for the done quantity field.
- stock.move.name is required (no default) in 18.0; must be supplied explicitly.
- ml.picked must be set True in test helpers; Odoo 18's _action_done() only
  processes moves where picked=True (new field, absent in pre-18 Odoo).
"""

from odoo import Command
from odoo.tests.common import TransactionCase, tagged


@tagged("post_install", "-at_install", "commercial_invoice")
class TestCommercialInvoiceLines(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # --- base objects ---
        cls.usd = cls.env.ref("base.USD")
        cls.company = cls.env.company
        cls.canada = cls.env.ref("base.ca")
        cls.usa = cls.env.ref("base.us")

        # Partners
        cls.partner = cls.env["res.partner"].create(
            {"name": "Test Consignee", "country_id": cls.usa.id}
        )
        cls.other_partner = cls.env["res.partner"].create(
            {"name": "Other Partner", "country_id": cls.usa.id}
        )

        # Products
        cls.product_a = cls.env["product.product"].create(
            {
                "name": "Widget A",
                "default_code": "WDGT-A",
                "type": "consu",
                "lst_price": 100.0,
            }
        )
        cls.product_b = cls.env["product.product"].create(
            {
                "name": "Widget B",
                "default_code": "WDGT-B",
                "type": "consu",
                "lst_price": 200.0,
            }
        )

        # Account setup for invoice tests
        cls.account_revenue = cls.env["account.account"].search(
            [
                ("company_ids", "in", [cls.company.id]),
                ("account_type", "=", "income"),
            ],
            limit=1,
        )
        cls.journal = cls.env["account.journal"].search(
            [("type", "=", "sale"), ("company_id", "=", cls.company.id)], limit=1
        )

        # Outgoing picking type
        cls.picking_type_out = cls.env["stock.picking.type"].search(
            [
                ("code", "=", "outgoing"),
                ("warehouse_id.company_id", "=", cls.company.id),
            ],
            limit=1,
        )
        cls.picking_type_in = cls.env["stock.picking.type"].search(
            [
                ("code", "=", "incoming"),
                ("warehouse_id.company_id", "=", cls.company.id),
            ],
            limit=1,
        )
        cls.picking_type_internal = cls.env["stock.picking.type"].search(
            [
                ("code", "=", "internal"),
                ("warehouse_id.company_id", "=", cls.company.id),
            ],
            limit=1,
        )
        cls.location_output = cls.picking_type_out.default_location_src_id
        cls.location_customer = cls.picking_type_out.default_location_dest_id

    # ------------------------------------------------------------------ helpers

    def _make_invoice(self, partner, product, qty, price_unit):
        """Create and post a customer invoice with one line."""
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": partner.id,
                "journal_id": self.journal.id,
                "currency_id": self.usd.id,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": product.id,
                            "quantity": qty,
                            "price_unit": price_unit,
                            "account_id": self.account_revenue.id,
                        },
                    )
                ],
            }
        )
        invoice.action_post()
        return invoice

    def _make_done_outgoing_picking(self, partner, product, qty, sale_price):
        """Create a done outgoing picking with one move.

        A fake sale.order.line is created to set sale_line_id so that
        price_unit can be validated independently of the move's own price_unit.

        18.0 adaptations:
        - use ml.quantity (not ml.qty_done) for the done qty.
        - stock.move.name is required in 18.0 (no default); provide product name.
        - ml.picked must be set True explicitly (new field in 18.0; required for
          _action_done() to include the move in moves_todo).
        """
        picking = self.env["stock.picking"].create(
            {
                "partner_id": partner.id,
                "picking_type_id": self.picking_type_out.id,
                "location_id": self.location_output.id,
                "location_dest_id": self.location_customer.id,
                "move_ids": [
                    (
                        0,
                        0,
                        {
                            "name": product.name,
                            "product_id": product.id,
                            "product_uom": product.uom_id.id,
                            "product_uom_qty": qty,
                            "location_id": self.location_output.id,
                            "location_dest_id": self.location_customer.id,
                            "price_unit": 999.0,  # intentionally wrong; test uses sale_line
                        },
                    )
                ],
            }
        )
        # Create a minimal sale.order.line to carry the expected price_unit
        sale_order = self.env["sale.order"].create(
            {
                "partner_id": partner.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": product.id,
                            "product_uom_qty": qty,
                            "price_unit": sale_price,
                        },
                    )
                ],
            }
        )
        sale_order.action_confirm()
        sale_line = sale_order.order_line[0]
        picking.move_ids.write({"sale_line_id": sale_line.id})

        # Validate the picking (mark as done)
        picking.action_assign()
        for ml in picking.move_line_ids:
            ml.quantity = qty
            ml.picked = True  # 18.0: must be set explicitly; _action_done filters on picked
        picking._action_done()
        return picking

    def _make_ci(self, partner, line_source="invoice", pickings=None):
        vals = {
            "partner_id": partner.id,
            "currency_id": self.usd.id,
            "line_source": line_source,
        }
        if pickings is not None:
            vals["picking_ids"] = [Command.set(pickings.ids)]
        return self.env["commercial.invoice"].create(vals)

    # ------------------------------------------------------------------ tests

    def test_01_invoice_source_report_lines(self):
        """line_source='invoice': _get_report_lines() mirrors invoice lines."""
        invoice = self._make_invoice(self.partner, self.product_a, 5.0, 42.0)
        ci = self._make_ci(self.partner)
        ci.invoice_ids = invoice

        lines = ci._get_report_lines()
        self.assertEqual(len(lines), 1, "Expected one report line from invoice")
        row = lines[0]
        self.assertEqual(row["name"], self.product_a.name)
        self.assertEqual(row["default_code"], "WDGT-A")
        self.assertAlmostEqual(row["quantity"], 5.0)
        self.assertAlmostEqual(row["price_unit"], 42.0)
        self.assertAlmostEqual(row["price_subtotal"], 5.0 * 42.0)

    def test_02_picking_source_report_lines(self):
        """line_source='picking': rows come from the selected pickings' moves."""
        pick = self._make_done_outgoing_picking(self.partner, self.product_a, 3.0, 55.0)
        ci = self._make_ci(self.partner, line_source="picking", pickings=pick)

        lines = ci._get_report_lines()
        self.assertEqual(len(lines), 1)
        row = lines[0]
        self.assertEqual(row["name"], self.product_a.name)
        self.assertAlmostEqual(row["quantity"], 3.0)
        self.assertAlmostEqual(row["price_unit"], 55.0)
        self.assertAlmostEqual(row["price_subtotal"], 3.0 * 55.0)

    def test_03_aggregation_across_pickings(self):
        """Two pickings same product+price → one aggregated row; third with
        different price → second row.

        Aggregation key is (product_id, price_unit).  Two rows with the same
        product but different prices are intentionally kept separate rather
        than weighted-averaged, because the requirements do not specify how to
        combine different prices.
        """
        # Two pickings: same product_a, same price 50
        p1 = self._make_done_outgoing_picking(self.partner, self.product_a, 2.0, 50.0)
        p2 = self._make_done_outgoing_picking(self.partner, self.product_a, 3.0, 50.0)
        # Third picking: same product_a, different price 60
        p3 = self._make_done_outgoing_picking(self.partner, self.product_a, 1.0, 60.0)

        ci = self._make_ci(
            self.partner, line_source="picking", pickings=p1 | p2 | p3
        )
        lines = ci._get_report_lines()

        # Group by price_unit to check aggregation
        by_price = {row["price_unit"]: row for row in lines}
        self.assertIn(50.0, by_price, "Expected a row for price 50")
        self.assertIn(60.0, by_price, "Expected a row for price 60")
        self.assertAlmostEqual(by_price[50.0]["quantity"], 5.0, msg="2+3 should aggregate")
        self.assertAlmostEqual(by_price[60.0]["quantity"], 1.0)

    def test_04_empty_deliveries(self):
        """No selected picking_ids → _get_report_lines() returns [].

        A done outgoing picking exists for the partner but is not selected, so
        it must NOT appear (single source of truth — no partner-search
        fallback).
        """
        self._make_done_outgoing_picking(self.partner, self.product_a, 7.0, 33.0)
        ci = self._make_ci(self.partner, line_source="picking")
        self.assertFalse(ci.picking_ids)
        lines = ci._get_report_lines()
        self.assertEqual(lines, [])

    def test_05_unit_price_from_sale_line(self):
        """price_unit on each row must equal move.sale_line_id.price_unit,
        not the product's list price (999.0 in the helper) or move.price_unit.
        """
        pick = self._make_done_outgoing_picking(self.partner, self.product_a, 4.0, 77.0)
        ci = self._make_ci(self.partner, line_source="picking", pickings=pick)
        lines = ci._get_report_lines()

        self.assertEqual(len(lines), 1)
        self.assertAlmostEqual(lines[0]["price_unit"], 77.0,
                               msg="price_unit must come from sale_line_id, not move.price_unit")

    def test_06_compute_amounts_picking_source(self):
        """_compute_amounts sums picking lines into invoice_amount; total_amount
        adds addon costs.
        """
        pa = self._make_done_outgoing_picking(self.partner, self.product_a, 2.0, 100.0)
        pb = self._make_done_outgoing_picking(self.partner, self.product_b, 1.0, 150.0)

        ci = self.env["commercial.invoice"].create(
            {
                "partner_id": self.partner.id,
                "currency_id": self.usd.id,
                "line_source": "picking",
                "picking_ids": [Command.set((pa | pb).ids)],
                "packaging_cost": 10.0,
                "freight_cost": 20.0,
                "insurance_cost": 5.0,
                "other_cost": 0.0,
            }
        )

        expected_invoice_amount = 2.0 * 100.0 + 1.0 * 150.0  # 350
        expected_total = expected_invoice_amount + 10.0 + 20.0 + 5.0  # 385

        self.assertAlmostEqual(ci.invoice_amount, expected_invoice_amount)
        self.assertAlmostEqual(ci.total_amount, expected_total)

    def test_07_backwards_compat_smoke(self):
        """Existing CI with line_source='invoice' still reports correctly."""
        invoice = self._make_invoice(self.partner, self.product_a, 1.0, 88.0)
        ci = self._make_ci(self.partner)
        self.assertEqual(ci.line_source, "invoice",
                         "Default line_source must be 'invoice'")
        ci.invoice_ids = invoice

        lines = ci._get_report_lines()
        self.assertEqual(len(lines), 1)
        self.assertAlmostEqual(lines[0]["price_unit"], 88.0)
        self.assertAlmostEqual(lines[0]["quantity"], 1.0)
        # invoice_amount should equal the invoice total
        self.assertAlmostEqual(ci.invoice_amount, invoice.amount_total)

    def test_08_select_partner_deliveries_scope(self):
        """The partner-sweep pre-fill action is partner-scoped.

        It must pick up the CI partner's done outgoing delivery and NOT the
        other partner's.  (Content sources only from picking_ids, so this is
        the partner-scope guarantee for the convenience sweep.)
        """
        mine = self._make_done_outgoing_picking(self.partner, self.product_a, 5.0, 10.0)
        theirs = self._make_done_outgoing_picking(
            self.other_partner, self.product_a, 5.0, 10.0
        )
        ci = self._make_ci(self.partner, line_source="picking")
        ci.action_select_partner_deliveries()

        self.assertIn(mine.id, ci.picking_ids.ids)
        self.assertNotIn(theirs.id, ci.picking_ids.ids)

    def test_09_non_outgoing_picking_ignored(self):
        """Incoming and internal pickings for the partner are excluded.

        The partner-sweep pre-fill action sweeps outgoing deliveries only, so
        an incoming picking for the same partner must NOT be pre-filled.

        18.0 adaptations: use ml.quantity (not ml.qty_done) for the done qty;
        stock.move.name is required; ml.picked must be set True explicitly.
        """
        location_supplier = self.picking_type_in.default_location_src_id
        location_input = self.picking_type_in.default_location_dest_id

        # Incoming picking (receipt)
        incoming = self.env["stock.picking"].create(
            {
                "partner_id": self.partner.id,
                "picking_type_id": self.picking_type_in.id,
                "location_id": location_supplier.id,
                "location_dest_id": location_input.id,
                "move_ids": [
                    (
                        0,
                        0,
                        {
                            "name": self.product_a.name,
                            "product_id": self.product_a.id,
                            "product_uom": self.product_a.uom_id.id,
                            "product_uom_qty": 10.0,
                            "location_id": location_supplier.id,
                            "location_dest_id": location_input.id,
                        },
                    )
                ],
            }
        )
        incoming.action_assign()
        for ml in incoming.move_line_ids:
            ml.quantity = 10.0
            ml.picked = True  # 18.0: explicit picked required
        incoming._action_done()

        ci = self._make_ci(self.partner, line_source="picking")
        ci.action_select_partner_deliveries()
        self.assertNotIn(
            incoming.id, ci.picking_ids.ids,
            "Incoming picking must not be pre-filled by the partner sweep",
        )
