from odoo.tests import tagged
from odoo.exceptions import ValidationError
from datetime import date
from dateutil.relativedelta import relativedelta

from odoo.fields import Command

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestOrganizationalUnit(AccountTestInvoicingCommon):
    """
    Core integration tests for organizational.unit (Customer Account) functionality.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        group_sale = cls.env.ref("sales_team.group_sale_salesman")
        cls.env.user.groups_id = [Command.link(group_sale.id)]
        cls.partner_model = cls.env["res.partner"]
        cls.ou_model = cls.env["organizational.unit"]
        cls.sale_order_model = cls.env["sale.order"]
        cls.account_move_model = cls.env["account.move"]
        cls.crm_lead_model = cls.env["crm.lead"]
        cls.product_model = cls.env["product.product"]

        # Create a test product
        cls.product = cls.product_model.create(
            {
                "name": "Test Product",
                "list_price": 100.0,
            }
        )

        # Set up accounting journal for invoice tests
        cls.company = cls.env.company
        cls.sale_journal = cls.env["account.journal"].search(
            [("type", "=", "sale"), ("company_id", "=", cls.company.id)], limit=1
        )
        if not cls.sale_journal:
            cls.sale_journal = cls.env["account.journal"].create(
                {
                    "name": "Test Sales Journal",
                    "type": "sale",
                    "code": "TSALE",
                    "company_id": cls.company.id,
                }
            )

    # =========================================================================
    # Core Model Tests (Not UC-specific)
    # =========================================================================

    def test_ou_model_basic_functionality(self):
        """Test basic OU model functionality and constraints."""
        # Test creating OU with owner
        company = self.partner_model.create(
            {
                "name": "Test Company",
                "is_company": True,
            }
        )
        ou = self.ou_model.search([("owner_id", "=", company.id)])
        
        self.assertTrue(ou.id, "OU should be created for company")
        self.assertEqual(ou.name, "Test Company", "OU name should match company")
        self.assertEqual(ou.owner_id, company, "OU owner should be the company")

    def test_ou_model_fields_exist(self):
        """Test that required OU model fields exist."""
        company = self.partner_model.create(
            {
                "name": "Test Company",
                "is_company": True,
            }
        )
        ou = self.ou_model.search([("owner_id", "=", company.id)])
        
        # Check key fields exist
        self.assertTrue(hasattr(ou, 'name'), "OU should have name field")
        self.assertTrue(hasattr(ou, 'owner_id'), "OU should have owner_id field")
        self.assertTrue(hasattr(ou, 'parent_id'), "OU should have parent_id field")
        self.assertTrue(hasattr(ou, 'child_ids'), "OU should have child_ids field")
        self.assertTrue(hasattr(ou, 'member_ids'), "OU should have member_ids field")
        self.assertTrue(hasattr(ou, 'user_id'), "OU should have user_id field")

    def test_ou_constraints(self):
        """Test OU model constraints."""
        # Test recursion prevention
        company = self.partner_model.create(
            {
                "name": "Test Company",
                "is_company": True,
            }
        )
        ou = self.ou_model.search([("owner_id", "=", company.id)])
        
        with self.assertRaises(ValidationError):
            ou.write({"parent_id": ou.id})

    # =========================================================================
    # Post-Install Validation
    # Ensures _create_ous_for_existing_partners works correctly
    # =========================================================================

    def test_create_ous_for_existing_partners_is_idempotent(self):
        """_create_ous_for_existing_partners should not create duplicates."""
        # Create a company - OU is auto-created
        company = self.partner_model.create(
            {
                "name": "Test Company",
                "is_company": True,
            }
        )
        ou = self.ou_model.search([("owner_id", "=", company.id)])
        self.assertEqual(len(ou), 1)

        # Run the init function again - should not create duplicate
        self.ou_model._create_ous_for_existing_partners()

        ou_after = self.ou_model.search([("owner_id", "=", company.id)])
        self.assertEqual(len(ou_after), 1, "Should not create duplicate OUs")

    def test_all_top_level_companies_have_ou(self):
        """After module install, all top-level companies should have an OU."""
        # Get all top-level company partners
        top_level_companies = self.partner_model.search(
            [
                ("is_company", "=", True),
                ("parent_id", "=", False),
            ]
        )

        for company in top_level_companies:
            ou = self.ou_model.search([("owner_id", "=", company.id)])
            self.assertEqual(
                len(ou), 1, f"Company '{company.name}' should have exactly one OU"
            )

    # =========================================================================
    # Cron and Searchability Tests
    # Ensures stored computed fields work correctly for searching/filtering
    # =========================================================================

    def test_cron_refresh_metrics(self):
        """_cron_refresh_metrics should run without errors."""
        # Create an OU with some data
        company = self.partner_model.create(
            {
                "name": "Cron Test Company",
                "is_company": True,
            }
        )
        ou = self.ou_model.search([("owner_id", "=", company.id)])
        self.assertTrue(ou)

        # Run the cron - should not raise
        self.ou_model._cron_refresh_metrics()

    def test_stored_fields_are_searchable(self):
        """Stored computed fields should be searchable."""
        # Create company and OU
        company = self.partner_model.create(
            {
                "name": "Search Test Company",
                "is_company": True,
            }
        )
        ou = self.ou_model.search([("owner_id", "=", company.id)])

        # Create an invoice to generate YTD sales
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
                            "name": "Test Product",
                            "quantity": 1,
                            "price_unit": 1000.0,
                        },
                    )
                ],
            }
        )
        invoice.action_post()

        # Force recompute
        ou._compute_sales_metrics()

        # Search by YTD sales - should find the OU
        found = self.ou_model.search(
            [
                ("ytd_sales", ">", 0),
                ("owner_id", "=", company.id),
            ]
        )
        self.assertEqual(found, ou, "Should find OU by ytd_sales search")

    def test_search_filter_ytd_growth(self):
        """Search filter for YTD growth should work."""
        # Create company with positive growth
        company = self.partner_model.create(
            {
                "name": "Growth Test Company",
                "is_company": True,
            }
        )
        ou = self.ou_model.search([("owner_id", "=", company.id)])

        # Create current year invoice
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
                            "name": "Test Product",
                            "quantity": 1,
                            "price_unit": 5000.0,
                        },
                    )
                ],
            }
        )
        invoice.action_post()

        # Force recompute
        ou._compute_sales_metrics()

        # With no prior year sales, change_pct should be 1.0 (100% growth)
        self.assertEqual(ou.ytd_sales_change_pct, 1.0)

        # Search for growth accounts
        growth_accounts = self.ou_model.search(
            [
                ("ytd_sales_change_pct", ">", 0),
                ("owner_id", "=", company.id),
            ]
        )
        self.assertEqual(growth_accounts, ou)

    def test_search_filter_open_quotations(self):
        """Search filter for open quotations should work."""
        company = self.partner_model.create(
            {
                "name": "Quotation Test Company",
                "is_company": True,
            }
        )
        ou = self.ou_model.search([("owner_id", "=", company.id)])

        # Create a draft quotation
        self.env["sale.order"].create(
            {
                "partner_id": company.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "product_uom_qty": 1,
                            "price_unit": 100.0,
                        },
                    )
                ],
            }
        )

        # Force recompute
        ou._compute_quotation_metrics()

        # Search for accounts with open quotations
        found = self.ou_model.search(
            [
                ("open_quotations_count", ">", 0),
                ("owner_id", "=", company.id),
            ]
        )
        self.assertEqual(found, ou)

    def test_search_filter_open_opportunities(self):
        """Search filter for open opportunities should work."""
        company = self.partner_model.create(
            {
                "name": "Opportunity Test Company",
                "is_company": True,
            }
        )
        ou = self.ou_model.search([("owner_id", "=", company.id)])

        # Create an open opportunity
        self.env["crm.lead"].create(
            {
                "name": "Test Opportunity",
                "partner_id": company.id,
                "type": "opportunity",
                "probability": 50,
                "expected_revenue": 10000.0,
            }
        )

        # Force recompute
        ou._compute_opportunity_metrics()

        # Search for accounts with open opportunities
        found = self.ou_model.search(
            [
                ("open_opportunities_count", ">", 0),
                ("owner_id", "=", company.id),
            ]
        )
        self.assertEqual(found, ou)
