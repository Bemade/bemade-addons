from odoo.tests import tagged
from odoo.exceptions import ValidationError
from datetime import date
from dateutil.relativedelta import relativedelta

from odoo.addons.crm_account_management.tests.common import OUTestCommon


@tagged("post_install", "-at_install")
class TestUS01Dashboard(OUTestCommon):
    """
    US-01: View Customer Account Dashboard
    
    As a salesperson, I want to view a customer account dashboard showing key metrics and trends, 
    so I can quickly assess account health and identify opportunities.
    
    Acceptance Criteria:
    - Display YTD sales $ vs same period last year
    - Display open quotations count and $, won quotations count and $
    - Display open sales orders count and $
    - Display open opportunities count and $ vs won opportunities
    - Show buying trends graph (monthly/quarterly)
    - Show top products purchased
    - Can click through to detailed records (drill-down)
    - Metrics aggregate from all partners in the account
    
    Phase 2.1 Enhancements (Client Feedback 2026-02-11):
    - Drill-Down Capability: Enable clicking on dashboard numbers and graph bars to view detailed records
    - Configurable Reference Date: Allow setting reference date for dashboard calculations (calendar vs fiscal year)
    - Average Gross Profit %: Display average gross profit percentage on customer account dashboard
    
    Requirements Covered:
    - Dashboard metrics display
    - YTD calculations with comparisons
    - Sales funnel metrics (quotations, orders, opportunities)
    - Drill-down navigation
    - Configurable date calculations
    - Gross profit analytics
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner_model = cls.env["res.partner"]
        cls.ou_model = cls.env["organizational.unit"]
        cls.sale_order_model = cls.env["sale.order"]
        cls.account_move_model = cls.env["account.move"]
        cls.crm_lead_model = cls.env["crm.lead"]
        cls.product_model = cls.env["product.product"]

        # Create test products
        cls.product = cls.product_model.create(
            {
                "name": "Test Product",
                "list_price": 100.0,
                "standard_price": 60.0,  # Cost for gross profit calculation
            }
        )
        cls.product2 = cls.product_model.create(
            {
                "name": "Expensive Product",
                "list_price": 500.0,
                "standard_price": 300.0,  # Cost for gross profit calculation
            }
        )

    # =========================================================================
    # Original US-01 Tests
    # AC: Display YTD sales $ vs same period last year
    # =========================================================================

    def test_ytd_sales_from_invoices(self):
        """YTD sales should be calculated from posted invoices."""
        company = self.partner_model.create(
            {
                "name": "Test Company",
                "is_company": True,
            }
        )
        ou = self.ou_model.search([("owner_id", "=", company.id)])

        # Create and post an invoice
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

        ou.invalidate_recordset()
        self.assertGreater(ou.ytd_sales, 0, "YTD sales should reflect posted invoice")

    def test_ytd_sales_excludes_prior_year(self):
        """YTD sales should not include invoices from prior year."""
        company = self.partner_model.create(
            {
                "name": "Test Company",
                "is_company": True,
            }
        )
        ou = self.ou_model.search([("owner_id", "=", company.id)])

        # Create invoice dated last year
        last_year = date.today() - relativedelta(years=1, days=1)
        invoice = self.env["account.move"].create(
            {
                "partner_id": company.id,
                "move_type": "out_invoice",
                "invoice_date": last_year,
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

        ou.invalidate_recordset()
        self.assertEqual(ou.ytd_sales, 0.0, "YTD sales should not include prior year invoices")

    def test_ytd_sales_change_calculation(self):
        """YTD sales change should compare current year to prior year."""
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
                        },
                    )
                ],
            }
        )
        current_invoice.action_post()

        ou.invalidate_recordset()
        # With no prior year sales, change should be 100% (1.0)
        self.assertEqual(ou.ytd_sales_change_pct, 1.0, "Should show 100% growth with no prior year sales")

    # =========================================================================
    # Quotations Tests
    # AC: Display open quotations count and $, won quotations count and $
    # =========================================================================

    def test_open_quotations_count(self):
        """Open quotations count should reflect draft/sent orders."""
        company = self.partner_model.create(
            {
                "name": "Test Company",
                "is_company": True,
            }
        )
        ou = self.ou_model.search([("owner_id", "=", company.id)])

        # Create quotations
        self._make_order(
            {
                "partner_id": company.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "product_uom_qty": 1,
                        },
                    )
                ],
            }
        )
        self._make_order(
            {
                "partner_id": company.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product2.id,
                            "product_uom_qty": 2,
                        },
                    )
                ],
            }
        )

        ou.invalidate_recordset()
        self.assertEqual(ou.open_quotations_count, 2, "Should have 2 open quotations")

    def test_won_quotations_ytd(self):
        """Won quotations should count confirmed orders this year."""
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
                            "product_uom_qty": 1,
                        },
                    )
                ],
            }
        )
        order.action_confirm()

        ou.invalidate_recordset()
        self.assertEqual(ou.won_quotations_count, 1, "Should have 1 won quotation")
        self.assertGreater(
            ou.won_quotations_amount, 0, "Won quotation amount should be > 0"
        )

    # =========================================================================
    # Orders Tests
    # AC: Display open sales orders count and $
    # =========================================================================

    def test_open_orders_count(self):
        """Open orders count should reflect confirmed but not invoiced orders."""
        company = self.partner_model.create(
            {
                "name": "Test Company",
                "is_company": True,
            }
        )
        ou = self.ou_model.search([("owner_id", "=", company.id)])

        # Create and confirm an order
        order = self._make_order(
            {
                "partner_id": company.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "product_uom_qty": 1,
                        },
                    )
                ],
            }
        )
        order.action_confirm()

        ou.invalidate_recordset()
        self.assertEqual(ou.open_orders_count, 1, "Should have 1 open order")
        self.assertGreater(ou.open_orders_amount, 0, "Open orders amount should be > 0")

    # =========================================================================
    # Opportunities Tests
    # AC: Display open opportunities count and $ vs won opportunities
    # =========================================================================

    def test_open_opportunities_count(self):
        """Open opportunities should count leads with 0 < probability < 100."""
        company = self.partner_model.create(
            {
                "name": "Test Company",
                "is_company": True,
            }
        )
        ou = self.ou_model.search([("owner_id", "=", company.id)])

        self.crm_lead_model.create(
            {
                "name": "Open Opportunity",
                "partner_id": company.id,
                "type": "opportunity",
                "probability": 50,
                "expected_revenue": 5000.0,
            }
        )

        ou.invalidate_recordset()
        self.assertEqual(
            ou.open_opportunities_count, 1, "Should have 1 open opportunity"
        )
        self.assertEqual(
            ou.open_opportunities_amount,
            5000.0,
            "Open opportunity amount should be 5000",
        )

    # =========================================================================
    # Aggregation Tests
    # AC: Metrics aggregate from all partners in the account
    # =========================================================================

    def test_metrics_aggregate_from_child_partners(self):
        """Dashboard metrics should aggregate from owner and child partners."""
        company = self.partner_model.create(
            {
                "name": "Test Company",
                "is_company": True,
            }
        )
        contact = self.partner_model.create(
            {
                "name": "Contact",
                "parent_id": company.id,
            }
        )
        ou = self.ou_model.search([("owner_id", "=", company.id)])

        # Create invoice for contact
        invoice = self.env["account.move"].create(
            {
                "partner_id": contact.id,
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
        invoice.action_post()

        ou.invalidate_recordset()
        self.assertEqual(ou.ytd_sales, 1000.0, "Should aggregate from child partner")

    def test_metrics_aggregate_from_child_ous(self):
        """Dashboard metrics should aggregate from child OUs."""
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
                            "tax_ids": False,
                        },
                    )
                ],
            }
        )
        invoice.action_post()

        parent_ou.invalidate_recordset()
        self.assertEqual(parent_ou.ytd_sales, 1000.0, "Should aggregate from child OU")

    # =========================================================================
    # Drill-Down Tests
    # AC: Can click through to detailed records (drill-down)
    # =========================================================================

    def test_action_view_quotations(self):
        """action_view_quotations should return window action."""
        company = self.partner_model.create(
            {
                "name": "Test Company",
                "is_company": True,
            }
        )
        ou = self.ou_model.search([("owner_id", "=", company.id)])

        action = ou.action_view_quotations()
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "sale.order")

    def test_action_view_orders(self):
        """action_view_orders should return window action."""
        company = self.partner_model.create(
            {
                "name": "Test Company",
                "is_company": True,
            }
        )
        ou = self.ou_model.search([("owner_id", "=", company.id)])

        action = ou.action_view_orders()
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "sale.order")

    def test_action_view_opportunities(self):
        """action_view_opportunities should return window action."""
        company = self.partner_model.create(
            {
                "name": "Test Company",
                "is_company": True,
            }
        )
        ou = self.ou_model.search([("owner_id", "=", company.id)])

        action = ou.action_view_opportunities()
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "crm.lead")

    def test_action_view_invoices(self):
        """action_view_invoices should return window action."""
        company = self.partner_model.create(
            {
                "name": "Test Company",
                "is_company": True,
            }
        )
        ou = self.ou_model.search([("owner_id", "=", company.id)])

        action = ou.action_view_invoices()
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "account.move")

    # =========================================================================
    # Phase 2.1 Enhancement: Configurable Reference Date
    # AC: Allow setting reference date for dashboard calculations (calendar vs fiscal year)
    # =========================================================================

    def test_fiscal_year_start_date_field(self):
        """OU should have fiscal_year_start_date field for configurable reference date."""
        company = self.partner_model.create(
            {
                "name": "Test Company",
                "is_company": True,
            }
        )
        ou = self.ou_model.search([("owner_id", "=", company.id)])

        # Check field exists
        self.assertTrue(hasattr(ou, 'fiscal_year_start_date'), "OU should have fiscal_year_start_date field")

        # Test setting custom fiscal year start (April 1st)
        custom_date = date(2024, 4, 1)
        ou.write({"fiscal_year_start_date": custom_date})
        self.assertEqual(ou.fiscal_year_start_date, custom_date, "Should save custom fiscal year start")

    # =========================================================================
    # Phase 2.1 Enhancement: Average Gross Profit %
    # AC: Display average gross profit percentage on customer account dashboard
    # =========================================================================

    def test_avg_gross_profit_percentage_computed(self):
        """OU should compute average gross profit percentage from sales."""
        company = self.partner_model.create(
            {
                "name": "Test Company",
                "is_company": True,
            }
        )
        ou = self.ou_model.search([("owner_id", "=", company.id)])

        # Create and confirm orders with known margins
        # Product 1: 100 price, 60 cost = 40% margin
        # Product 2: 500 price, 300 cost = 40% margin
        order1 = self._make_order(
            {
                "partner_id": company.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "product_uom_qty": 1,
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
                            "product_uom_qty": 1,
                        },
                    )
                ],
            }
        )
        order2.action_confirm()

        # Create invoices to realize the gross profit
        for order in [order1, order2]:
            invoice = order._create_invoices()
            invoice.action_post()

        ou.invalidate_recordset()
        
        # Check that field exists and is computed
        self.assertTrue(hasattr(ou, 'avg_gross_profit_percentage'), "OU should have avg_gross_profit_percentage field")
        self.assertIsInstance(ou.avg_gross_profit_percentage, float, "Should be a float value")
        # Should be approximately 40% (0.4)
        self.assertAlmostEqual(ou.avg_gross_profit_percentage, 0.4, places=2, msg="Should compute 40% gross profit")

    def test_avg_gross_profit_different_margins(self):
        """Average gross profit should handle different product margins correctly."""
        company = self.partner_model.create(
            {
                "name": "Test Company",
                "is_company": True,
            }
        )
        ou = self.ou_model.search([("owner_id", "=", company.id)])

        # Create products with different margins
        high_margin_product = self.product_model.create(
            {
                "name": "High Margin Product",
                "list_price": 200.0,
                "standard_price": 80.0,  # 60% margin
            }
        )
        low_margin_product = self.product_model.create(
            {
                "name": "Low Margin Product", 
                "list_price": 100.0,
                "standard_price": 90.0,  # 10% margin
            }
        )

        # Create orders
        order1 = self._make_order(
            {
                "partner_id": company.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": high_margin_product.id,
                            "product_uom_qty": 1,
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
                            "product_id": low_margin_product.id,
                            "product_uom_qty": 1,
                        },
                    )
                ],
            }
        )
        order2.action_confirm()

        # Create invoices
        for order in [order1, order2]:
            invoice = order._create_invoices()
            invoice.action_post()

        ou.invalidate_recordset()
        
        # Average should be (60% + 10%) / 2 = 35%
        expected_avg = (0.6 + 0.1) / 2
        self.assertAlmostEqual(ou.avg_gross_profit_percentage, expected_avg, places=2, 
                          msg="Should average different margins correctly")
