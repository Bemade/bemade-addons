from odoo.tests import tagged
from odoo.exceptions import ValidationError
from datetime import date
from dateutil.relativedelta import relativedelta

from odoo.addons.crm_account_management.tests.common import OUTestCommon


@tagged("post_install", "-at_install")
class TestUS02BuyingTrends(OUTestCommon):
    """
    US-02: View Buying Trends
    
    As a salesperson, I want to see buying trends for a customer account, 
    so I can identify patterns and opportunities.
    
    Acceptance Criteria:
    - Show sales by period (monthly, quarterly) over time (graph data)
    - Compare current period to prior year
    - Show top products purchased
    - Filterable by date range (date_from, date_to params)
    - Aggregate from child OUs
    
    Phase 2.1 Enhancement (Client Feedback 2026-02-11):
    - Yearly Graph Option: Add "yearly" period option to the customer account dashboard graph
    
    Requirements Covered:
    - Buying trend analysis
    - Period-based sales aggregation
    - Top products analysis
    - Date range filtering
    - Enhanced period options
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_model = cls.env["res.partner"]
        cls.ou_model = cls.env["organizational.unit"]
        cls.sale_order_model = cls.env["sale.order"]
        cls.account_move_model = cls.env["account.move"]
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
    # Original US-02 Tests
    # AC: Show sales by month/quarter over time (graph data)
    # AC: Compare current period to prior year
    # =========================================================================

    def test_get_sales_by_period_monthly(self):
        """get_sales_by_period should return sales aggregated by month."""
        company = self.partner_model.create(
            {
                "name": "Test Company",
                "is_company": True,
            }
        )
        ou = self.ou_model.search([("owner_id", "=", company.id)])

        # Create and post an invoice this month
        invoice = self.env["account.move"].create(
            {
                "partner_id": company.id,
                "move_type": "out_invoice",
                "invoice_date": date.today(),
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "quantity": 1,
                            "price_unit": 1000.0,
                        },
                    )
                ],
            }
        )
        invoice.action_post()

        sales_data = ou.get_sales_by_period(period="month", periods=12)
        self.assertIsInstance(sales_data, list, "Should return a list")
        total = sum(d.get("total", 0) or 0 for d in sales_data)
        self.assertGreater(total, 0, "Total sales should be greater than 0")

    def test_get_sales_by_period_quarterly(self):
        """get_sales_by_period should return sales aggregated by quarter."""
        company = self.partner_model.create(
            {
                "name": "Test Company",
                "is_company": True,
            }
        )
        ou = self.ou_model.search([("owner_id", "=", company.id)])

        # Create and post an invoice this quarter
        invoice = self.env["account.move"].create(
            {
                "partner_id": company.id,
                "move_type": "out_invoice",
                "invoice_date": date.today(),
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "quantity": 1,
                            "price_unit": 1000.0,
                        },
                    )
                ],
            }
        )
        invoice.action_post()

        sales_data = ou.get_sales_by_period(period="quarter", periods=4)
        self.assertIsInstance(sales_data, list, "Should return a list")
        total = sum(d.get("total", 0) or 0 for d in sales_data)
        self.assertGreater(total, 0, "Total sales should be greater than 0")

    def test_get_sales_by_period_date_range(self):
        """get_sales_by_period should respect date range parameters."""
        company = self.partner_model.create(
            {
                "name": "Test Company",
                "is_company": True,
            }
        )
        ou = self.ou_model.search([("owner_id", "=", company.id)])

        # Create invoice in the past
        past_date = date.today() - relativedelta(months=6)
        past_invoice = self.env["account.move"].create(
            {
                "partner_id": company.id,
                "move_type": "out_invoice",
                "invoice_date": past_date,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "quantity": 1,
                            "price_unit": 500.0,
                            "tax_ids": False,
                        },
                    )
                ],
            }
        )
        past_invoice.action_post()

        # Create recent invoice
        recent_invoice = self.env["account.move"].create(
            {
                "partner_id": company.id,
                "move_type": "out_invoice",
                "invoice_date": date.today(),
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product2.id,
                            "quantity": 1,
                            "price_unit": 1000.0,
                            "tax_ids": False,
                        },
                    )
                ],
            }
        )
        recent_invoice.action_post()

        # Query only recent period
        date_from = date.today() - relativedelta(months=3)
        recent_sales = ou.get_sales_by_period(period="month", periods=12, date_from=date_from)

        # Should only include recent sales
        total = sum(d.get("total", 0) or 0 for d in recent_sales)
        self.assertEqual(total, 1000.0, "Should only include recent invoice amount")

    def test_get_sales_by_period_aggregates_child_ous(self):
        """get_sales_by_period should aggregate from child OUs."""
        parent_company = self.partner_model.create(
            {
                "name": "Parent Company",
                "is_company": True,
            }
        )
        child_company = self.partner_model.create(
            {
                "name": "Child Company",
                "is_company": True,
            }
        )

        parent_ou = self.ou_model.search([("owner_id", "=", parent_company.id)])
        child_ou = self.ou_model.search([("owner_id", "=", child_company.id)])
        child_ou.write({"parent_id": parent_ou.id})

        # Create invoice for child company
        invoice = self.env["account.move"].create(
            {
                "partner_id": child_company.id,
                "move_type": "out_invoice",
                "invoice_date": date.today(),
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "quantity": 1,
                            "price_unit": 1000.0,
                        },
                    )
                ],
            }
        )
        invoice.action_post()

        # Parent OU should see child's sales
        sales_data = parent_ou.get_sales_by_period(period="month", periods=12)
        total = sum(d.get("total", 0) or 0 for d in sales_data)
        self.assertGreater(total, 0, "Parent OU should aggregate child sales")

    def test_get_sales_by_period_data_structure(self):
        """get_sales_by_period should return proper data structure."""
        company = self.partner_model.create(
            {
                "name": "Test Company",
                "is_company": True,
            }
        )
        ou = self.ou_model.search([("owner_id", "=", company.id)])

        sales_data = ou.get_sales_by_period(period="month", periods=12)
        self.assertIsInstance(sales_data, list, "Should return a list")
        
        if sales_data:  # Only check if data exists
            first_period = sales_data[0]
            self.assertIn("period", first_period, "Should have period field")
            self.assertIn("total", first_period, "Should have total field")

    # =========================================================================
    # Top Products Tests
    # AC: Show top products purchased
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

    # =========================================================================
    # Phase 2.1 Enhancement: Yearly Graph Option
    # AC: Add "yearly" period option to the customer account dashboard graph
    # =========================================================================

    def test_get_sales_by_period_yearly(self):
        """get_sales_by_period should support yearly period option."""
        company = self.partner_model.create(
            {
                "name": "Test Company",
                "is_company": True,
            }
        )
        ou = self.ou_model.search([("owner_id", "=", company.id)])

        # Create and post an invoice this year
        invoice = self.env["account.move"].create(
            {
                "partner_id": company.id,
                "move_type": "out_invoice",
                "invoice_date": date.today(),
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "quantity": 1,
                            "price_unit": 1000.0,
                        },
                    )
                ],
            }
        )
        invoice.action_post()

        sales_data = ou.get_sales_by_period(period="year", periods=5)
        self.assertIsInstance(sales_data, list, "Should return a list")
        # Should have data for the current year
        self.assertTrue(len(sales_data) > 0, "Should return yearly sales data")
        
        # Check data structure
        if sales_data:
            first_period = sales_data[0]
            self.assertIn("period", first_period, "Should have period field")
            self.assertIn("total", first_period, "Should have total field")

    def test_get_sales_by_period_yearly_multiple_years(self):
        """get_sales_by_period should return data for multiple years."""
        company = self.partner_model.create(
            {
                "name": "Test Company",
                "is_company": True,
            }
        )
        ou = self.ou_model.search([("owner_id", "=", company.id)])

        # Create invoice for current year
        current_invoice = self.env["account.move"].create(
            {
                "partner_id": company.id,
                "move_type": "out_invoice",
                "invoice_date": date.today(),
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "quantity": 1,
                            "price_unit": 1000.0,
                            "tax_ids": False,
                        },
                    )
                ],
            }
        )
        current_invoice.action_post()

        # Create invoice for last year
        last_year_date = date.today() - relativedelta(years=1)
        last_year_invoice = self.env["account.move"].create(
            {
                "partner_id": company.id,
                "move_type": "out_invoice",
                "invoice_date": last_year_date,
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product2.id,
                            "quantity": 1,
                            "price_unit": 500.0,
                            "tax_ids": False,
                        },
                    )
                ],
            }
        )
        last_year_invoice.action_post()

        sales_data = ou.get_sales_by_period(period="year", periods=3)
        self.assertEqual(len(sales_data), 2, "Should have data for 2 years")

        # Should include both years
        total = sum(d.get("total", 0) or 0 for d in sales_data)
        self.assertEqual(total, 1500.0, "Should include both years' sales")

    def test_get_top_products_with_date_range(self):
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

    def test_get_top_products_aggregates_from_child_ous(self):
        """get_top_products should aggregate from child OUs."""
        parent_company = self.partner_model.create(
            {
                "name": "Parent Company",
                "is_company": True,
            }
        )
        child_company = self.partner_model.create(
            {
                "name": "Child Company",
                "is_company": True,
            }
        )

        parent_ou = self.ou_model.search([("owner_id", "=", parent_company.id)])
        child_ou = self.ou_model.search([("owner_id", "=", child_company.id)])
        child_ou.write({"parent_id": parent_ou.id})

        # Create order for child company
        order = self._make_order(
            {
                "partner_id": child_company.id,
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

        top_products = parent_ou.get_top_products(limit=10)
        self.assertEqual(len(top_products), 1, "Should find product from child OU")
        self.assertEqual(top_products[0]["product_name"], "Test Product")

    # =========================================================================
    # Data Structure Validation
    # =========================================================================

    def test_top_products_data_structure(self):
        """get_top_products should return proper data structure."""
        company = self.partner_model.create(
            {
                "name": "Test Company",
                "is_company": True,
            }
        )
        ou = self.ou_model.search([("owner_id", "=", company.id)])

        order = self._make_order(
            {
                "partner_id": company.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "product_uom_qty": 3,
                        },
                    )
                ],
            }
        )
        order.action_confirm()

        top_products = ou.get_top_products(limit=1)
        self.assertEqual(len(top_products), 1)
        
        product_data = top_products[0]
        required_fields = ["product_id", "product_name", "total_qty", "total_amount"]
        for field in required_fields:
            self.assertIn(field, product_data, f"Should include {field} field")
        
        self.assertEqual(product_data["product_id"], self.product.product_tmpl_id.id)
        self.assertEqual(product_data["product_name"], "Test Product")
        self.assertEqual(product_data["total_qty"], 3.0)
        self.assertGreater(product_data["total_amount"], 0)

    def test_sales_by_period_data_structure(self):
        """get_sales_by_period should return proper data structure."""
        company = self.partner_model.create(
            {
                "name": "Test Company",
                "is_company": True,
            }
        )
        ou = self.ou_model.search([("owner_id", "=", company.id)])

        invoice = self.env["account.move"].create(
            {
                "partner_id": company.id,
                "move_type": "out_invoice",
                "invoice_date": date.today(),
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "quantity": 1,
                            "price_unit": 1000.0,
                        },
                    )
                ],
            }
        )
        invoice.action_post()

        sales_data = ou.get_sales_by_period(period="month", periods=12)
        if sales_data:  # Only check if we have data
            period_data = sales_data[0]
            required_fields = ["period", "total"]
            for field in required_fields:
                self.assertIn(field, period_data, f"Should include {field} field")
            self.assertIsInstance(period_data["period"], date)
            self.assertIsInstance(period_data["total"], (int, float))

    # =========================================================================
    # Regression tests for task-3181: buying-trends widget layout + RPC errors
    # =========================================================================

    def test_buying_trends_widget_at_sheet_level(self):
        """The buying_trends widget must mount at the form sheet level, not
        inside a <group>, so it can span the full form width.
        """
        from lxml import etree

        view = self.env.ref("crm_account_management.organizational_unit_view_form")
        arch = etree.fromstring(view.arch)
        widgets = arch.xpath("//widget[@name='buying_trends']")
        self.assertEqual(
            len(widgets), 1,
            "There should be exactly one buying_trends widget on the form",
        )
        widget = widgets[0]
        # Walk up the ancestor chain: must hit <sheet> before any <group>.
        ancestor = widget.getparent()
        while ancestor is not None and ancestor.tag != "sheet":
            self.assertNotEqual(
                ancestor.tag, "group",
                "buying_trends widget must NOT be wrapped in a <group> "
                "(causes the narrow-column layout regression)",
            )
            ancestor = ancestor.getparent()
        self.assertIsNotNone(
            ancestor,
            "buying_trends widget must live inside the form <sheet>",
        )

    def test_buying_trends_header_layout_classes(self):
        """The card-header rows must keep a defensive flex layout: titles
        carry text-truncate min-w-0 and selectors carry flex-shrink-0 so the
        title and period selector cannot overlap at narrow widths.
        """
        # The QWeb template is registered under web.assets_backend, not
        # as an ir.ui.view, so read the asset file directly.
        import os
        from odoo.modules import module as odoo_module
        path = os.path.join(
            odoo_module.get_module_path("crm_account_management"),
            "static", "src", "xml", "buying_trends_widget.xml",
        )
        with open(path, "r", encoding="utf-8") as fh:
            content = fh.read()

        # Both card headers retain the flex container classes.
        self.assertEqual(
            content.count(
                'card-header d-flex justify-content-between align-items-center'
            ),
            2,
            "Both card headers must use the flex layout container",
        )
        # Both <strong> titles must carry the truncation/min-width classes.
        self.assertIn(
            '<strong class="text-truncate min-w-0 me-2">Sales Trend</strong>',
            content,
        )
        self.assertIn(
            '<strong class="text-truncate min-w-0 me-2">Products Purchased</strong>',
            content,
        )
        # Both <select>s must be flex-shrink-0 so they keep their natural width.
        self.assertEqual(
            content.count('flex-shrink-0'), 2,
            "Both card-header <select>s must carry flex-shrink-0",
        )

    def test_products_rpc_error_surfaces(self):
        """The products empty branch must distinguish a true empty result
        from an RPC failure: the QWeb template must render an explicit
        error message (driven by state.productsError) before falling back
        to 'No product data available'.
        """
        import os
        from odoo.modules import module as odoo_module
        path = os.path.join(
            odoo_module.get_module_path("crm_account_management"),
            "static", "src", "xml", "buying_trends_widget.xml",
        )
        with open(path, "r", encoding="utf-8") as fh:
            xml_content = fh.read()

        self.assertIn(
            't-elif="state.productsError"', xml_content,
            "Products card must render a distinct error branch when "
            "state.productsError is non-empty",
        )
        self.assertIn(
            't-esc="state.productsError"', xml_content,
            "The error branch must surface state.productsError to the user",
        )

        js_path = os.path.join(
            odoo_module.get_module_path("crm_account_management"),
            "static", "src", "js", "buying_trends_widget.js",
        )
        with open(js_path, "r", encoding="utf-8") as fh:
            js_content = fh.read()

        # productsError state field must exist and be assigned in the
        # top-products catch block (split from the sales-trend block).
        self.assertIn("productsError", js_content)
        self.assertIn("this.state.productsError", js_content)
        # Two independent try/catch blocks now wrap the two RPCs.
        self.assertGreaterEqual(
            js_content.count("} catch (error) {"), 2,
            "loadData must split the two RPC awaits into independent "
            "try/catch blocks so a top-products failure does not "
            "silently coexist with a successful sales-trend fetch",
        )
