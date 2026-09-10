from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestReplenishmentCost(TransactionCase):
    """Regression tests for the replenishment cost columns
    (cost_supplier / cost_subtotal) on stock.warehouse.orderpoint.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.warehouse = cls.env["stock.warehouse"].search([], limit=1)
        cls.vendor_a = cls.env["res.partner"].create({"name": "Vendor A"})
        cls.vendor_b = cls.env["res.partner"].create({"name": "Vendor B"})

    def _make_product(self, name, sellers=None):
        """sellers: list of (partner, sequence, price)."""
        vals = {
            "name": name,
            "is_storable": True,
        }
        if sellers:
            vals["seller_ids"] = [
                (0, 0, {
                    "partner_id": partner.id,
                    "sequence": sequence,
                    "price": price,
                })
                for (partner, sequence, price) in sellers
            ]
        return self.env["product.product"].create(vals)

    def _make_orderpoint(self, product, qty_to_order=None):
        op = self.env["stock.warehouse.orderpoint"].create({
            "product_id": product.id,
            "warehouse_id": self.warehouse.id,
            "location_id": self.warehouse.lot_stock_id.id,
        })
        if qty_to_order is not None:
            # Deterministic To-Order qty independent of live forecast.
            op.qty_to_order_manual = qty_to_order
            op.invalidate_recordset(["qty_to_order"])
        return op

    def test_cost_supplier_primary_seller(self):
        """Primary (lowest-sequence) seller wins, NOT the cheapest."""
        product = self._make_product(
            "Two-vendor product",
            sellers=[
                (self.vendor_a, 1, 10.0),  # primary by sequence
                (self.vendor_b, 2, 7.0),   # cheaper but not primary
            ],
        )
        op = self._make_orderpoint(product)
        self.assertEqual(
            op.cost_supplier, 10.0,
            "cost_supplier must be the first seller by sequence (10.0), "
            "not the cheapest (7.0).",
        )

    def test_cost_supplier_no_seller(self):
        """No seller -> cost_supplier is 0.0."""
        product = self._make_product("No-vendor product")
        op = self._make_orderpoint(product)
        self.assertEqual(op.cost_supplier, 0.0)

    def test_cost_subtotal(self):
        """cost_subtotal == qty_to_order * cost_supplier."""
        product = self._make_product(
            "Single-vendor product",
            sellers=[(self.vendor_a, 1, 5.0)],
        )
        op = self._make_orderpoint(product, qty_to_order=3.0)
        self.assertEqual(op.qty_to_order, 3.0)
        self.assertEqual(op.cost_supplier, 5.0)
        self.assertEqual(op.cost_subtotal, 15.0)
        self.assertEqual(
            op.cost_subtotal,
            op.qty_to_order * op.cost_supplier,
        )

    def test_cost_subtotal_zero_when_no_seller(self):
        """No seller + a To-Order qty -> cost_subtotal is 0.0."""
        product = self._make_product("No-vendor product 2")
        op = self._make_orderpoint(product, qty_to_order=4.0)
        self.assertEqual(op.cost_subtotal, 0.0)
