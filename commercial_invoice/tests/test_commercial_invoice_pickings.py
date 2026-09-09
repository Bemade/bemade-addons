# License: LGPL-3
# Author: Bemade Inc. (Marc Durepos <marc@bemade.org>)
"""Tests for the explicit picking-selection commercial-invoice feature.

Ported into the shared base module from verajet_commercial_invoice (task 3705
MR-1).  Acceptance criteria covered:

1. create_from_pickings produces a CI with picking_ids stored, line_source
   set to 'picking', consignee/importer/currency derived, and the delivery
   header (po_numbers / carrier_id / ship_date) computed.
2. The multi-select stock.picking server action
   (action_create_commercial_invoice) creates a CI from the selected
   deliveries and returns a form action pointing at it.
3. Single source of truth: report lines come ONLY from the explicit
   picking_ids (even unvalidated).  With picking_ids empty the picking path
   yields NO lines — there is NO partner-search fallback (task 3705
   refinement).
4. "Select all deliveries for this partner" action: populates picking_ids
   with the partner's done outgoing deliveries (a pre-fill the user can trim,
   not auto-content), partner-scoped.
5. The existing invoice-sourced path is unchanged (line_source='invoice').
6. action_confirm guard: a CI with neither invoices nor pickings raises;
   one with pickings confirms.

18.0 adaptations:
- stock.move.line uses `quantity` (not `qty_done`) for the done quantity field.
- ml.picked must be set True in test helpers; Odoo 18's _action_done() only
  processes moves where picked=True (new field, absent in pre-18 Odoo).
"""

from datetime import datetime, timedelta

from odoo import Command
from odoo.exceptions import UserError
from odoo.tests.common import TransactionCase, tagged
from odoo.tools.misc import mute_logger


@tagged("post_install", "-at_install", "commercial_invoice")
class TestCommercialInvoicePickings(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.usd = cls.env.ref("base.USD")
        cls.company = cls.env.company

        cls.partner = cls.env["res.partner"].create(
            {"name": "US Customer", "email": "ap@uscustomer.test"}
        )
        cls.other_partner = cls.env["res.partner"].create(
            {"name": "Other Customer"}
        )

        cls.product = cls.env["product.product"].create(
            {
                "name": "Widget A",
                "default_code": "WDGT-A",
                "type": "consu",
                "is_storable": True,
                "list_price": 100.0,
            }
        )
        # Non-storable so done outgoing pickings validate without reservation
        # (the partner-search-fallback tests need a *done* picking).
        cls.product_consu = cls.env["product.product"].create(
            {
                "name": "Widget C",
                "default_code": "WDGT-C",
                "type": "consu",
                "list_price": 100.0,
            }
        )

        cls.picking_type_out = cls.env["stock.picking.type"].search(
            [
                ("code", "=", "outgoing"),
                ("warehouse_id.company_id", "=", cls.company.id),
            ],
            limit=1,
        )
        cls.loc_src = cls.picking_type_out.default_location_src_id
        cls.loc_dest = cls.picking_type_out.default_location_dest_id

        # Account setup for the invoice-path regression test.
        cls.account_revenue = cls.env["account.account"].search(
            [
                ("company_ids", "in", [cls.company.id]),
                ("account_type", "=", "income"),
            ],
            limit=1,
        )
        cls.journal = cls.env["account.journal"].search(
            [("type", "=", "sale"), ("company_id", "=", cls.company.id)],
            limit=1,
        )

    # ----------------------------------------------------------------- helpers

    @classmethod
    def _make_sale_with_picking(cls, ref, product, qty, price):
        """Confirm a SO, returning its (unvalidated) delivery picking."""
        so = cls.env["sale.order"].create(
            {
                "partner_id": cls.partner.id,
                "client_order_ref": ref,
                "order_line": [
                    Command.create(
                        {
                            "product_id": product.id,
                            "product_uom_qty": qty,
                            "price_unit": price,
                        }
                    )
                ],
            }
        )
        so.action_confirm()
        return so, so.picking_ids[:1]

    def _make_done_outgoing_picking(self, partner, product, qty, sale_price):
        """A done outgoing picking carrying a sale_line_id price.

        18.0 adaptations:
        - use ml.quantity (not ml.qty_done) for the done qty.
        - ml.picked must be set True explicitly; Odoo 18's _action_done() only
          processes moves where picked=True (new field, absent in pre-18 Odoo).
        """
        so = self.env["sale.order"].create(
            {
                "partner_id": partner.id,
                "order_line": [
                    Command.create(
                        {
                            "product_id": product.id,
                            "product_uom_qty": qty,
                            "price_unit": sale_price,
                        }
                    )
                ],
            }
        )
        so.action_confirm()
        picking = so.picking_ids[:1]
        picking.action_assign()
        for ml in picking.move_line_ids:
            ml.quantity = qty
            ml.picked = True  # 18.0: explicit picked required for _action_done
        picking._action_done()
        return picking

    def _make_invoice(self, partner, product, qty, price_unit):
        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": partner.id,
                "journal_id": self.journal.id,
                "currency_id": self.usd.id,
                "invoice_line_ids": [
                    Command.create(
                        {
                            "product_id": product.id,
                            "quantity": qty,
                            "price_unit": price_unit,
                            "account_id": self.account_revenue.id,
                        }
                    )
                ],
            }
        )
        invoice.action_post()
        return invoice

    # ------------------------------------------------------------------- tests

    def test_create_from_pickings_stores_and_computes(self):
        """create_from_pickings: picking_ids stored, header + totals computed."""
        so1, pick1 = self._make_sale_with_picking("PO-A", self.product, 10, 100.0)
        so2, pick2 = self._make_sale_with_picking("PO-B", self.product, 5, 100.0)
        now = datetime.now()
        pick1.scheduled_date = now + timedelta(days=2)
        pick2.scheduled_date = now + timedelta(days=1)  # earliest

        ci = self.env["commercial.invoice"].create_from_pickings(pick1 | pick2)

        self.assertEqual(set(ci.picking_ids.ids), {pick1.id, pick2.id})
        self.assertEqual(ci.partner_id, self.partner.commercial_partner_id)
        self.assertEqual(ci.importer_id, self.partner.commercial_partner_id)
        # Header (computed from the selected deliveries)
        self.assertIn("PO-A", ci.po_numbers)
        self.assertIn("PO-B", ci.po_numbers)
        self.assertEqual(ci.ship_date, pick2.scheduled_date.date())

    def test_server_action_creates_ci(self):
        """The multi-select stock.picking action builds a CI and returns it."""
        _so1, pick1 = self._make_sale_with_picking("PO-S1", self.product, 3, 100.0)
        _so2, pick2 = self._make_sale_with_picking("PO-S2", self.product, 4, 100.0)

        result = (pick1 | pick2).action_create_commercial_invoice()

        self.assertEqual(result["res_model"], "commercial.invoice")
        ci = self.env["commercial.invoice"].browse(result["res_id"])
        self.assertEqual(set(ci.picking_ids.ids), {pick1.id, pick2.id})

    def test_server_action_rejects_non_outgoing(self):
        """The action raises when no outgoing picking is selected."""
        # Build an internal/incoming picking type-less selection by faking it:
        # an empty recordset of non-outgoing pickings → UserError.
        incoming_type = self.env["stock.picking.type"].search(
            [
                ("code", "=", "incoming"),
                ("warehouse_id.company_id", "=", self.company.id),
            ],
            limit=1,
        )
        picking = self.env["stock.picking"].create(
            {
                "partner_id": self.partner.id,
                "picking_type_id": incoming_type.id,
                "location_id": incoming_type.default_location_src_id.id,
                "location_dest_id": incoming_type.default_location_dest_id.id,
            }
        )
        with self.assertRaises(UserError):
            picking.action_create_commercial_invoice()

    def test_selection_first_lines(self):
        """Explicit picking_ids drive the report lines (selection-first)."""
        _so1, pick1 = self._make_sale_with_picking("PO-X", self.product, 6, 100.0)
        ci = self.env["commercial.invoice"].create(
            {
                "partner_id": self.partner.id,
                "currency_id": self.usd.id,
                "line_source": "picking",
                "picking_ids": [Command.set(pick1.ids)],
            }
        )
        lines = ci._get_report_lines()
        self.assertEqual(len(lines), 1)
        self.assertAlmostEqual(lines[0]["quantity"], 6.0)
        self.assertAlmostEqual(lines[0]["price_unit"], 100.0)
        self.assertAlmostEqual(lines[0]["price_subtotal"], 600.0)
        # With line_source='picking', _compute_amounts uses the delivery path.
        self.assertAlmostEqual(ci.invoice_amount, 600.0)
        self.assertAlmostEqual(ci.total_amount, 600.0)

    def test_selection_first_uses_unvalidated_pickings(self):
        """Selected, NOT-yet-validated pickings still produce lines.

        The partner-search fallback only ever sees done pickings, so this is
        the distinguishing behaviour of selection-first: the picking here is
        confirmed but not validated (state != 'done').
        """
        _so, pick = self._make_sale_with_picking("PO-U", self.product, 8, 100.0)
        self.assertNotEqual(pick.state, "done")
        ci = self.env["commercial.invoice"].create(
            {
                "partner_id": self.partner.id,
                "currency_id": self.usd.id,
                "line_source": "picking",
                "picking_ids": [Command.set(pick.ids)],
            }
        )
        lines = ci._get_report_lines()
        self.assertEqual(len(lines), 1)
        self.assertAlmostEqual(lines[0]["quantity"], 8.0)

    def test_empty_picking_ids_yields_no_lines(self):
        """No picking_ids set → NO lines (no partner-search fallback).

        A done outgoing picking exists for the partner, but because it is not
        explicitly selected it must NOT be pulled onto the document.
        ``picking_ids`` is the single source of truth (task 3705 refinement).
        """
        self._make_done_outgoing_picking(self.partner, self.product_consu, 2.0, 100.0)
        ci = self.env["commercial.invoice"].create(
            {
                "partner_id": self.partner.id,
                "currency_id": self.usd.id,
                "line_source": "picking",
            }
        )
        self.assertFalse(ci.picking_ids)
        self.assertEqual(
            ci._get_report_lines(), [],
            "Empty picking_ids must NOT fall back to a partner search",
        )
        self.assertAlmostEqual(
            ci.invoice_amount, 0.0,
            msg="No selected deliveries → zero picking-derived amount",
        )

    def test_select_partner_deliveries_action_populates(self):
        """The action pre-fills picking_ids with the partner's done deliveries.

        It POPULATES the M2M (a convenience the user can then trim) — it does
        not compute/store content by itself; content still flows through
        picking_ids via _get_report_lines.
        """
        pick = self._make_done_outgoing_picking(
            self.partner, self.product_consu, 2.0, 100.0
        )
        ci = self.env["commercial.invoice"].create(
            {
                "partner_id": self.partner.id,
                "currency_id": self.usd.id,
                "line_source": "picking",
            }
        )
        self.assertFalse(ci.picking_ids)

        ci.action_select_partner_deliveries()

        self.assertIn(pick.id, ci.picking_ids.ids)
        # Now that picking_ids is populated, content sources from it.
        lines = ci._get_report_lines()
        self.assertEqual(len(lines), 1)
        self.assertAlmostEqual(lines[0]["quantity"], 2.0)
        self.assertAlmostEqual(lines[0]["price_unit"], 100.0)

        # Pre-fill is writable/trimmable: removing a row drops its content.
        ci.picking_ids = [Command.unlink(pick.id)]
        self.assertFalse(ci.picking_ids)
        self.assertEqual(ci._get_report_lines(), [])

    def test_select_partner_deliveries_is_partner_scoped(self):
        """The pre-fill sweep only picks up the CI partner's deliveries."""
        own = self._make_done_outgoing_picking(
            self.partner, self.product_consu, 4.0, 100.0
        )
        other = self._make_done_outgoing_picking(
            self.other_partner, self.product_consu, 9.0, 100.0
        )
        ci = self.env["commercial.invoice"].create(
            {
                "partner_id": self.partner.id,
                "currency_id": self.usd.id,
                "line_source": "picking",
            }
        )
        ci.action_select_partner_deliveries()
        self.assertIn(own.id, ci.picking_ids.ids)
        self.assertNotIn(other.id, ci.picking_ids.ids)

    def test_invoice_path_unchanged(self):
        """The invoice-sourced path still works and ignores pickings."""
        invoice = self._make_invoice(self.partner, self.product, 5.0, 42.0)
        ci = self.env["commercial.invoice"].create(
            {
                "partner_id": self.partner.id,
                "currency_id": self.usd.id,
                "line_source": "invoice",
                "invoice_ids": [Command.set(invoice.ids)],
            }
        )
        lines = ci._get_report_lines()
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0]["default_code"], "WDGT-A")
        self.assertAlmostEqual(lines[0]["price_unit"], 42.0)
        self.assertAlmostEqual(ci.invoice_amount, invoice.amount_total)

    @mute_logger("odoo.models")
    def test_action_confirm_guard(self):
        """action_confirm requires at least one invoice or one delivery."""
        empty = self.env["commercial.invoice"].create(
            {"partner_id": self.partner.id, "currency_id": self.usd.id}
        )
        with self.assertRaises(UserError):
            empty.action_confirm()

        _so, pick = self._make_sale_with_picking("PO-C", self.product, 1, 100.0)
        ci = self.env["commercial.invoice"].create(
            {
                "partner_id": self.partner.id,
                "currency_id": self.usd.id,
                "line_source": "picking",
                "picking_ids": [Command.set(pick.ids)],
            }
        )
        ci.action_confirm()
        self.assertEqual(ci.state, "done")
