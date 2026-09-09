from odoo.tests import tagged
from odoo.exceptions import ValidationError
from datetime import date
from dateutil.relativedelta import relativedelta

from odoo.addons.crm_account_management.tests.common import OUTestCommon


@tagged("post_install", "-at_install")
class TestUS20TopProducts(OUTestCommon):
    """
    US-20: View Top Products by Customer
    
    As a salesperson, I want to see the top products purchased by a customer account, 
    so I can understand their buying patterns.
    
    Acceptance Criteria:
    - List of products ranked by $ or quantity
    - Filterable by date range
    - Shows trend (up/down vs prior period)
    
    Phase 2.1 Enhancement (Client Feedback 2026-02-11):
    - Full Product List with Sorting: Replace top 12 products limitation with sortable table showing all purchased products
    
    Requirements Covered:
    - Product purchasing analysis
    - Trend analysis capabilities
    - Enhanced product list functionality
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_model = cls.env["res.partner"]
        cls.ou_model = cls.env["organizational.unit"]
        cls.sale_order_model = cls.env["sale.order"]
        cls.product_model = cls.env["product.product"]

        # Create test products
        cls.product = cls.product_model.create(
            {
                "name": "Test Product",
                "list_price": 100.0,
            }
        )
        cls.product2 = cls.product_model.create(
            {
                "name": "Expensive Product",
                "list_price": 500.0,
            }
        )

    # =========================================================================
    # Original US-20 Tests
    # AC: List of products ranked by $ or quantity
    # AC: Filterable by date range
    # =========================================================================

    def test_get_top_products(self):
        """get_top_products should return products ranked by sales amount."""
        company = self.partner_model.create(
            {
                "name": "Test Company",
                "is_company": True,
            }
        )
        ou = self.ou_model.search([("owner_id", "=", company.id)])

        # Create and confirm orders
        order1 = self._make_order(
            {
                "partner_id": company.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "product_uom_qty": 10,
                        },
                    )
                ],
            }
        )
        order1.action_confirm()

        order2 = self._make_order(
            {
                "partner_id": company.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product2.id,
                            "product_uom_qty": 5,
                        },
                    )
                ],
            }
        )
        order2.action_confirm()

        top_products = ou.get_top_products(limit=10)
        self.assertEqual(len(top_products), 2, "Should have 2 products")
        # Expensive product should be first (500 * 5 = 2500 > 100 * 10 = 1000)
        self.assertEqual(top_products[0]["product_name"], "Expensive Product")

    def test_get_top_products_date_range(self):
        """get_top_products should respect date range parameters."""
        company = self.partner_model.create(
            {
                "name": "Test Company",
                "is_company": True,
            }
        )
        ou = self.ou_model.search([("owner_id", "=", company.id)])

        # Create order in the past
        past_date = date.today() - relativedelta(months=6)
        order = self._make_order(
            {
                "partner_id": company.id,
                "date_order": past_date,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "product_uom_qty": 5,
                        },
                    )
                ],
            }
        )
        order.action_confirm()
        # Restore past date (action_confirm resets date_order to now)
        order.date_order = past_date

        # Create recent order
        recent_order = self._make_order(
            {
                "partner_id": company.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product2.id,
                            "product_uom_qty": 3,
                        },
                    )
                ],
            }
        )
        recent_order.action_confirm()

        # Query only recent period
        date_from = date.today() - relativedelta(months=3)
        recent_products = ou.get_top_products(date_from=date_from, limit=10)

        self.assertEqual(len(recent_products), 1, "Should only find recent products")
        self.assertEqual(recent_products[0]["product_name"], "Expensive Product")

    def test_get_top_products_no_partners(self):
        """get_top_products should return empty list when no partners."""
        parent_company = self.partner_model.create(
            {
                "name": "Parent Company",
                "is_company": True,
            }
        )
        parent_ou = self.ou_model.search([("owner_id", "=", parent_company.id)])

        child_ou = self.ou_model.create(
            {
                "name": "Empty Department",
                "parent_id": parent_ou.id,
                "owner_id": False,
            }
        )

        result = child_ou.get_top_products()
        self.assertEqual(result, [], "Should return empty list")

    # =========================================================================
    # Phase 2.1 Enhancement: Full Product List with Sorting
    # AC: Replace top 12 products limitation with sortable table showing all purchased products
    # =========================================================================

    def test_get_all_products_unlimited(self):
        """get_all_products should return all products without limit when limit=None."""
        company = self.partner_model.create(
            {
                "name": "Test Company",
                "is_company": True,
            }
        )
        ou = self.ou_model.search([("owner_id", "=", company.id)])

        # Create 15 products to exceed current 12 product limit
        products = []
        for i in range(15):
            product = self.product_model.create(
                {
                    "name": f"Product {i+1}",
                    "list_price": 100.0 + i,
                }
            )
            products.append(product)

        # Create orders for all products
        for i, product in enumerate(products):
            order = self._make_order(
                {
                    "partner_id": company.id,
                    "order_line": [
                        (
                            0,
                            0,
                            {
                                "product_id": product.id,
                                "product_uom_qty": 1,
                            },
                        )
                    ],
                }
            )
            order.action_confirm()

        # Test unlimited product list
        all_products = ou.get_top_products(limit=None)
        self.assertEqual(len(all_products), 15, "Should return all 15 products")

        # Test with limit still works
        limited_products = ou.get_top_products(limit=10)
        self.assertEqual(len(limited_products), 10, "Should respect limit when provided")

    def test_get_all_products_sorting(self):
        """get_all_products should support sorting by different fields."""
        company = self.partner_model.create(
            {
                "name": "Test Company",
                "is_company": True,
            }
        )
        ou = self.ou_model.search([("owner_id", "=", company.id)])

        # Create products with different prices and quantities
        product_a = self.product_model.create(
            {
                "name": "Low Price High Qty",
                "list_price": 50.0,
            }
        )
        product_b = self.product_model.create(
            {
                "name": "High Price Low Qty", 
                "list_price": 200.0,
            }
        )
        product_c = self.product_model.create(
            {
                "name": "Medium Price Medium Qty",
                "list_price": 100.0,
            }
        )

        # Create orders with different quantities
        order1 = self._make_order(
            {
                "partner_id": company.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": product_a.id,
                            "product_uom_qty": 10,  # High qty, low price = 500 total
                        },
                    )
                ],
            }
        )
        order1.action_confirm()

        order2 = self._make_order(
            {
                "partner_id": company.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": product_b.id,
                            "product_uom_qty": 1,  # Low qty, high price = 200 total
                        },
                    )
                ],
            }
        )
        order2.action_confirm()

        order3 = self._make_order(
            {
                "partner_id": company.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": product_c.id,
                            "product_uom_qty": 3,  # Medium qty, medium price = 300 total
                        },
                    )
                ],
            }
        )
        order3.action_confirm()

        # Test sorting by total_amount (default)
        by_amount = ou.get_top_products(sort_by="total_amount")
        self.assertEqual(by_amount[0]["product_name"], "Low Price High Qty")
        self.assertEqual(by_amount[2]["product_name"], "High Price Low Qty")

        # Test sorting by quantity
        by_quantity = ou.get_top_products(sort_by="total_qty")
        self.assertEqual(by_quantity[0]["product_name"], "Low Price High Qty")
        self.assertEqual(by_quantity[2]["product_name"], "High Price Low Qty")

        # Test sorting by name
        by_name = ou.get_top_products(sort_by="product_name")
        product_names = [p["product_name"] for p in by_name]
        self.assertEqual(product_names, sorted(product_names))

    # =========================================================================
    # Regression test for task-3181 — defect 3
    # AC: get_top_products tolerates large datasets without raising and
    # returns aggregated rows whose totals match a reference Python sum.
    # =========================================================================

    def test_get_top_products_large_dataset(self):
        """get_top_products must aggregate cleanly over 1000+ SOL rows
        spanning 100+ distinct products without timing out or raising.
        Validates the _read_group rewrite (defect 3 root-cause fix).
        """
        company = self.partner_model.create(
            {
                "name": "Large Account",
                "is_company": True,
            }
        )
        ou = self.ou_model.search([("owner_id", "=", company.id)])

        # Seed 120 distinct products.
        n_products = 120
        products = self.product_model.create([
            {
                "name": f"Bulk Product {i:03d}",
                "default_code": f"BULK-{i:03d}",
                "list_price": 10.0 + i,
            }
            for i in range(n_products)
        ])

        # Seed 1050 sale.order.lines (10 SOs of ~105 lines each).
        # _make_order keeps the API consistent with the rest of the suite.
        n_orders = 10
        lines_per_order = 105
        expected_total_qty = {p.product_tmpl_id.id: 0.0 for p in products}
        expected_total_amount = {p.product_tmpl_id.id: 0.0 for p in products}

        for o in range(n_orders):
            order_lines = []
            for li in range(lines_per_order):
                product = products[(o * lines_per_order + li) % n_products]
                qty = 1.0 + ((o + li) % 5)
                order_lines.append((0, 0, {
                    "product_id": product.id,
                    "product_uom_qty": qty,
                }))
                expected_total_qty[product.product_tmpl_id.id] += qty
                expected_total_amount[product.product_tmpl_id.id] += (
                    qty * product.list_price
                )
            order = self._make_order({
                "partner_id": company.id,
                "order_line": order_lines,
            })
            order.action_confirm()

        # Top-N call: must not raise, must respect limit.
        top10 = ou.get_top_products(limit=10)
        self.assertEqual(len(top10), 10, "Should respect limit=10")

        # Unlimited call: must return one row per distinct template.
        all_rows = ou.get_top_products(limit=None)
        self.assertEqual(
            len(all_rows), n_products,
            "Should aggregate to exactly one row per distinct product",
        )

        # Per-row totals must match the Python reference computed above.
        for row in all_rows:
            tmpl_id = row["product_id"]
            self.assertAlmostEqual(
                row["total_qty"], expected_total_qty[tmpl_id], places=2,
                msg=f"qty mismatch for tmpl {tmpl_id}",
            )
            self.assertAlmostEqual(
                row["total_amount"], expected_total_amount[tmpl_id], places=2,
                msg=f"amount mismatch for tmpl {tmpl_id}",
            )
