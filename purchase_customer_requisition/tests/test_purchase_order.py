from odoo.tests import TransactionCase, tagged, Form
from odoo import Command, fields
from datetime import datetime, timedelta


@tagged("post_install", "-at_install")
class TestPurchaseOrder(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.mto_route = cls.env.ref("stock.route_warehouse0_mto")
        cls.buy_route = cls.env.ref("purchase_stock.route_warehouse0_buy")
        cls.mto_route.active = True
        cls.supplier = cls.env.ref("base.res_partner_18")
        cls.client_1 = cls.env.ref("base.res_partner_2")
        cls.client_2 = cls.env.ref("base.res_partner_3")
        cls.client_3 = cls.env.ref("base.res_partner_4")
        cls.product_1 = cls.env["product.product"].create(
            {
                "name": "SuperProduct",
                "is_storable": True,
                "route_ids": [Command.set((cls.mto_route + cls.buy_route).ids)],
                "seller_ids": [
                    Command.create(
                        {
                            "partner_id": cls.supplier.id,
                            "price": 3000,
                        },
                    )
                ],
            }
        )

        cls.product_2 = cls.env["product.product"].create(
            {
                "name": "SuperProduct2",
                "is_storable": True,
                "route_ids": [Command.set((cls.mto_route + cls.buy_route).ids)],
                "seller_ids": [
                    Command.create(
                        {
                            "partner_id": cls.supplier.id,
                            "price": 5000,
                        },
                    )
                ],
            }
        )

        cls.agreement_1 = cls.env["purchase.requisition"].create(
            {
                "vendor_id": cls.supplier.id,
                "customer_ids": [Command.set([cls.client_1.id, cls.client_2.id])],
                "line_ids": [
                    Command.create(
                        {
                            "product_id": cls.product_1.id,
                            "product_qty": 100,
                            "price_unit": 1000,
                        }
                    ),
                    Command.create(
                        {
                            "product_id": cls.product_2.id,
                            "product_qty": 100,
                            "price_unit": 2000,
                        }
                    ),
                ],
                "date_start": fields.Date.today() - timedelta(days=100),
                "date_end": fields.Date.today() + timedelta(days=265),
            }
        )
        cls.agreement_1.action_confirm()
        cls.agreement_2 = cls.env["purchase.requisition"].create(
            {
                "vendor_id": cls.supplier.id,
                "customer_ids": [Command.set([cls.client_3.id])],
                "line_ids": [
                    Command.create(
                        {
                            "product_id": cls.product_1.id,
                            "product_qty": 100,
                            "price_unit": 1500,
                        }
                    ),
                ],
                "date_start": fields.Date.today() - timedelta(days=100),
                "date_end": fields.Date.today() + timedelta(days=265),
            }
        )
        cls.agreement_2.action_confirm()

    def test_one_purchase_order_line_gets_correct_agreement(self):
        sale_order = self.env["sale.order"].create(
            {
                "partner_id": self.client_1.id,
                "delivery_billing_mode": "ppc",
                "order_line": [
                    Command.create(
                        {
                            "product_id": self.product_1.id,
                            "product_uom_qty": 50,
                        }
                    )
                ],
            }
        )
        sale_order.with_context(skip_tax_warning=True).action_confirm()

        self.assertTrue(sale_order._get_purchase_orders())
        purchase_line = sale_order._get_purchase_orders()[0].order_line[0]
        self.assertEqual(purchase_line.order_id.partner_id, self.supplier)
        self.assertEqual(purchase_line.requisition_id, self.agreement_1)

    def test_competing_sale_orders_get_two_lines(self):
        purchase_order = self._generate_2_sales_1_purchase_clients_1_3()
        self.assertEqual(len(purchase_order.order_line), 2)
        self.assertEqual(
            purchase_order.order_line[0].requisition_id,
            self.agreement_1,
            f"PO line for Partner 1 should have requisition {self.agreement_1.name}, not {purchase_order.order_line[0].requisition_id.name}",
        )
        self.assertEqual(
            purchase_order.order_line[1].requisition_id,
            self.agreement_2,
            f"PO line for Partner 2 should have requisition {self.agreement_2.name}, not {purchase_order.order_line[1].requisition_id.name}"
            f"PO line has sale order {purchase_order.order_line[1].sale_order_id} and sale line {purchase_order.order_line[1].sale_line_id}"
            f"PO has sales orders {purchase_order._get_sale_orders()}"
            f"PO has requisition {purchase_order.requisition_id}",
        )

    def _generate_2_sales_1_purchase_clients_1_3(self):
        sale_order_1 = self.env["sale.order"].create(
            {
                "partner_id": self.client_1.id,
                "delivery_billing_mode": "ppc",
                "order_line": [
                    Command.create(
                        {
                            "product_id": self.product_1.id,
                            "product_uom_qty": 50,
                        }
                    )
                ],
            }
        )
        sale_order_1.with_context(skip_tax_warning=True).action_confirm()
        sale_order_2 = self.env["sale.order"].create(
            {
                "partner_id": self.client_3.id,
                "delivery_billing_mode": "ppc",
                "order_line": [
                    Command.create(
                        {
                            "product_id": self.product_1.id,
                            "product_uom_qty": 50,
                        }
                    )
                ],
            }
        )
        sale_order_2.with_context(skip_tax_warning=True).action_confirm()
        purchase_order = sale_order_1._get_purchase_orders()[0]
        return purchase_order

    def test_lines_from_multiple_sales_get_correct_pricing(self):
        purchase_order = self._generate_2_sales_1_purchase_clients_1_3()

        self.assertEqual(purchase_order.order_line[0].price_unit, 1000)
        self.assertEqual(purchase_order.order_line[1].price_unit, 1500)

    def test_removing_line_agreement_recomputes_pricing(self):
        purchase_order = self._generate_2_sales_1_purchase_clients_1_3()
        purchase_order.requisition_id = False

        line = purchase_order.order_line[0]
        line.requisition_id = False

        self.assertEqual(purchase_order.order_line[0].price_unit, 3000)

    def test_requisition_selection_state_and_validity(self):
        """Test that requisitions are only selected if they are confirmed and currently valid."""
        # Create a draft requisition
        draft_agreement = self.env["purchase.requisition"].create(
            {
                "vendor_id": self.supplier.id,
                "customer_ids": [Command.set([self.client_1.id])],
                "line_ids": [
                    Command.create(
                        {
                            "product_id": self.product_1.id,
                            "product_qty": 100,
                            "price_unit": 4000,
                        }
                    ),
                ],
                "date_start": fields.Date.today() - timedelta(days=100),
                "date_end": fields.Date.today() + timedelta(days=265),
            }
        )

        # Create an expired requisition
        expired_agreement = self.env["purchase.requisition"].create(
            {
                "vendor_id": self.supplier.id,
                "customer_ids": [Command.set([self.client_1.id])],
                "line_ids": [
                    Command.create(
                        {
                            "product_id": self.product_1.id,
                            "product_qty": 100,
                            "price_unit": 5000,
                        }
                    ),
                ],
                "date_start": fields.Date.today() - timedelta(days=200),
                "date_end": fields.Date.today() - timedelta(days=100),
            }
        )
        expired_agreement.action_confirm()

        # Create a future requisition
        future_agreement = self.env["purchase.requisition"].create(
            {
                "vendor_id": self.supplier.id,
                "customer_ids": [Command.set([self.client_1.id])],
                "line_ids": [
                    Command.create(
                        {
                            "product_id": self.product_1.id,
                            "product_qty": 100,
                            "price_unit": 6000,
                        }
                    ),
                ],
                "date_start": fields.Date.today() + timedelta(days=100),
                "date_end": fields.Date.today() + timedelta(days=200),
            }
        )
        future_agreement.action_confirm()

        # Create and confirm a sale order
        sale_order = self.env["sale.order"].create(
            {
                "partner_id": self.client_1.id,
                "delivery_billing_mode": "ppc",
                "order_line": [
                    Command.create(
                        {
                            "product_id": self.product_1.id,
                            "product_uom_qty": 50,
                        }
                    )
                ],
            }
        )
        sale_order.with_context(skip_tax_warning=True).action_confirm()

        # Verify that the purchase order line gets the correct agreement (agreement_1)
        purchase_order = sale_order._get_purchase_orders()[0]
        purchase_line = purchase_order.order_line[0]

        # Should select agreement_1 which is confirmed and currently valid
        self.assertEqual(
            purchase_line.requisition_id,
            self.agreement_1,
            "Purchase order line should select the confirmed and currently valid agreement",
        )
        self.assertEqual(
            purchase_line.price_unit,
            1000,
            "Purchase order line should have the price from the valid agreement",
        )

        # The other agreements should not be selected because:
        # - draft_agreement is not confirmed
        # - expired_agreement is outside its validity dates
        # - future_agreement hasn't started yet
        self.assertNotEqual(
            purchase_line.requisition_id,
            draft_agreement,
            "Draft agreement should not be selected",
        )
        self.assertNotEqual(
            purchase_line.requisition_id,
            expired_agreement,
            "Expired agreement should not be selected",
        )
        self.assertNotEqual(
            purchase_line.requisition_id,
            future_agreement,
            "Future agreement should not be selected",
        )

    # ------------------------------------------------------------------
    # Task 3421: consolidate same-product lines on merge regardless of date
    # ------------------------------------------------------------------
    def _make_draft_po(self, product, qty, date_planned, packaging=False):
        """Create a one-line draft PO for ``supplier``.

        ``date_planned`` is written AFTER creation: on create it is a stored
        compute (``_compute_price_unit_and_date_planned_and_name``) that derives
        the date from the seller and would clobber a value passed in vals. A
        direct write sticks (the compute only re-fires on product/qty/uom
        changes, not on ``date_planned`` itself).
        """
        line_vals = {
            "product_id": product.id,
            "product_qty": qty,
        }
        if packaging:
            line_vals["product_packaging_id"] = packaging.id
        order = self.env["purchase.order"].create(
            {
                "partner_id": self.supplier.id,
                "order_line": [Command.create(line_vals)],
            }
        )
        order.order_line.date_planned = date_planned
        return order

    def _real_lines(self, order, product):
        return order.order_line.filtered(
            lambda l: l.display_type not in ("line_note", "line_section")
            and l.product_id == product
        )

    def test_merge_consolidates_same_product_different_dates(self):
        now = datetime(2026, 6, 12, 12, 0, 0)
        later = now + timedelta(days=5)  # > 24h apart -> core keeps separate
        po_a = self._make_draft_po(self.product_1, 10, now)
        po_b = self._make_draft_po(self.product_1, 7, later)

        # Precondition: two separate draft orders, each one line, dates >24h apart.
        self.assertEqual(po_a.state, "draft")
        self.assertEqual(po_b.state, "draft")
        self.assertEqual(po_a.order_line.product_qty, 10)
        self.assertEqual(po_b.order_line.product_qty, 7)
        self.assertGreater(
            abs((po_a.order_line.date_planned - po_b.order_line.date_planned).total_seconds()),
            86400,
            "Precondition: the two lines' dates must be >24h apart",
        )

        (po_a + po_b).action_merge()

        survivor_order = po_a if po_a.state in ("draft", "sent") else po_b
        lines = self._real_lines(survivor_order, self.product_1)
        self.assertEqual(
            len(lines), 1, "Same-product lines must consolidate into ONE line"
        )
        self.assertEqual(lines.product_qty, 17, "Quantities must be summed (10 + 7)")
        self.assertEqual(
            lines.date_planned, now, "Consolidated line must keep the EARLIEST date"
        )
        self.assertEqual(
            survivor_order.date_planned, now, "Header date_planned must be the earliest"
        )

    def test_merge_preserves_move_dest_ids(self):
        now = datetime(2026, 6, 12, 12, 0, 0)
        later = now + timedelta(days=5)
        po_a = self._make_draft_po(self.product_1, 10, now)
        po_b = self._make_draft_po(self.product_1, 7, later)

        # Populate move_dest_ids on each line with a distinct draft stock.move.
        customer_loc = self.env.ref("stock.stock_location_customers")
        stock_loc = self.env.ref("stock.stock_location_stock")
        move_a = self.env["stock.move"].create(
            {
                "name": "demand A",
                "product_id": self.product_1.id,
                "product_uom_qty": 10,
                "product_uom": self.product_1.uom_id.id,
                "location_id": stock_loc.id,
                "location_dest_id": customer_loc.id,
            }
        )
        move_b = self.env["stock.move"].create(
            {
                "name": "demand B",
                "product_id": self.product_1.id,
                "product_uom_qty": 7,
                "product_uom": self.product_1.uom_id.id,
                "location_id": stock_loc.id,
                "location_dest_id": customer_loc.id,
            }
        )
        po_a.order_line.move_dest_ids = [Command.set([move_a.id])]
        po_b.order_line.move_dest_ids = [Command.set([move_b.id])]

        # Precondition: each line carries one distinct downstream move.
        self.assertEqual(po_a.order_line.move_dest_ids, move_a)
        self.assertEqual(po_b.order_line.move_dest_ids, move_b)
        expected = po_a.order_line.move_dest_ids | po_b.order_line.move_dest_ids
        self.assertEqual(len(expected), 2, "Precondition: two distinct downstream moves")

        (po_a + po_b).action_merge()

        survivor_order = po_a if po_a.state in ("draft", "sent") else po_b
        lines = self._real_lines(survivor_order, self.product_1)
        self.assertEqual(len(lines), 1, "Lines must consolidate into ONE line")
        self.assertEqual(
            lines.move_dest_ids,
            expected,
            "Consolidated line must keep BOTH downstream moves "
            "(procurement chain preserved) -- fails if consolidation open-codes unlink",
        )

    def test_merge_keeps_distinct_packaging_separate(self):
        now = datetime(2026, 6, 12, 12, 0, 0)
        later = now + timedelta(days=5)
        pack_a = self.env["product.packaging"].create(
            {"name": "Box of 5", "product_id": self.product_1.id, "qty": 5}
        )
        pack_b = self.env["product.packaging"].create(
            {"name": "Box of 10", "product_id": self.product_1.id, "qty": 10}
        )
        po_a = self._make_draft_po(self.product_1, 10, now, packaging=pack_a)
        po_b = self._make_draft_po(self.product_1, 7, later, packaging=pack_b)

        # Precondition: same product, dates >24h apart, but DIFFERENT packaging.
        self.assertEqual(po_a.order_line.product_packaging_id, pack_a)
        self.assertEqual(po_b.order_line.product_packaging_id, pack_b)
        self.assertNotEqual(
            po_a.order_line.product_packaging_id, po_b.order_line.product_packaging_id
        )

        (po_a + po_b).action_merge()

        survivor_order = po_a if po_a.state in ("draft", "sent") else po_b
        lines = self._real_lines(survivor_order, self.product_1)
        self.assertEqual(
            len(lines),
            2,
            "Lines with different packaging must stay SEPARATE "
            "(only the date clause is relaxed)",
        )
