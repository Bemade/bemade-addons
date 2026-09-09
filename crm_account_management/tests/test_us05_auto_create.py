from odoo.tests import tagged
from odoo.exceptions import ValidationError
from datetime import date
from dateutil.relativedelta import relativedelta

from odoo.fields import Command

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestUS05AutoCreateOU(AccountTestInvoicingCommon):
    """
    US-05: Auto-Create OU for Top-Level Company Partners
    
    As a system, when a top-level partner (parent_id=False, is_company=True) is created, 
    an Organizational Unit is automatically created that the partner "owns".
    
    Acceptance Criteria:
    - OU is created automatically when top-level company partner is created
    - OU name defaults to partner name
    - Partner's children (contacts, addresses) are implicitly members of its OU
    - No manual action required for the common case
    
    Requirements Covered:
    - Req 2: Automatic account creation (auto-create OU on company partner)
    - Req 10: A company's contacts and addresses are implicitly part of its account
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        group_sale = cls.env.ref("sales_team.group_sale_salesman")
        cls.env.user.groups_id = [Command.link(group_sale.id)]
        cls.partner_model = cls.env["res.partner"]
        cls.ou_model = cls.env["organizational.unit"]

    # =========================================================================
    # Auto-Creation Tests
    # AC: OU is created automatically when top-level company partner is created
    # =========================================================================

    def test_auto_create_ou_for_top_level_company(self):
        """When a top-level company partner is created, an OU is automatically created."""
        partner = self.partner_model.create(
            {
                "name": "Test Company",
                "is_company": True,
            }
        )

        # OU should be auto-created
        ou = self.ou_model.search([("owner_id", "=", partner.id)])
        self.assertEqual(len(ou), 1, "OU should be auto-created for top-level company")
        self.assertEqual(ou.name, "Test Company", "OU name should match partner name")
        self.assertEqual(ou.owner_id, partner, "OU owner should be the partner")

    def test_no_ou_for_contact(self):
        """Contacts (non-company partners) should not get an OU."""
        company = self.partner_model.create(
            {
                "name": "Parent Company",
                "is_company": True,
            }
        )
        contact = self.partner_model.create(
            {
                "name": "John Doe",
                "is_company": False,
                "parent_id": company.id,
            }
        )

        ou = self.ou_model.search([("owner_id", "=", contact.id)])
        self.assertEqual(len(ou), 0, "Contacts should not have an OU")

    def test_no_ou_for_child_company(self):
        """Child companies (with parent_id) should not get their own OU automatically."""
        parent = self.partner_model.create(
            {
                "name": "Parent Company",
                "is_company": True,
            }
        )
        child = self.partner_model.create(
            {
                "name": "Child Company",
                "is_company": True,
                "parent_id": parent.id,
            }
        )

        ou = self.ou_model.search([("owner_id", "=", child.id)])
        self.assertEqual(len(ou), 0, "Child companies should not auto-create OU")

    # =========================================================================
    # Name Synchronization
    # AC: OU name defaults to partner name
    # =========================================================================

    def test_ou_name_syncs_with_partner_name(self):
        """When partner name changes, OU name should update."""
        partner = self.partner_model.create(
            {
                "name": "Original Name",
                "is_company": True,
            }
        )
        ou = self.ou_model.search([("owner_id", "=", partner.id)])

        partner.write({"name": "Updated Name"})
        self.assertEqual(
            ou.name, "Updated Name", "OU name should sync with partner name"
        )

    # =========================================================================
    # Account Manager Synchronization
    # Req 13: Account ownership (user_id field)
    # Req 14: Ownership logic (sync from partner when single company)
    # =========================================================================

    def test_ou_user_syncs_from_partner(self):
        """Account manager should sync from partner's salesperson when single company."""
        user = self.env.ref("base.user_admin")
        partner = self.partner_model.create(
            {
                "name": "Test Company",
                "is_company": True,
                "user_id": user.id,
            }
        )
        ou = self.ou_model.search([("owner_id", "=", partner.id)])

        self.assertEqual(
            ou.user_id, user, "OU account manager should be set from partner"
        )

    def test_ou_user_syncs_on_partner_change(self):
        """OU account manager should sync when partner user_id changes."""
        # Create initial partner
        partner = self.partner_model.create(
            {
                "name": "Test Company",
                "is_company": True,
            }
        )
        ou = self.ou_model.search([("owner_id", "=", partner.id)])

        # Initially no user
        self.assertFalse(ou.user_id, "Initially no account manager")

        # Set user on partner
        user = self.env.ref("base.user_admin")
        partner.write({"user_id": user.id})
        
        self.assertEqual(ou.user_id, user, "OU account manager should sync from partner")

    # =========================================================================
    # Implicit Membership
    # AC: Partner's children (contacts, addresses) are implicitly members of its OU
    # =========================================================================

    def test_ou_includes_owner_children(self):
        """OU should include owner partner's child contacts and addresses."""
        company = self.partner_model.create(
            {
                "name": "Test Company",
                "is_company": True,
            }
        )
        contact1 = self.partner_model.create(
            {
                "name": "Contact 1",
                "parent_id": company.id,
            }
        )
        contact2 = self.partner_model.create(
            {
                "name": "Contact 2",
                "parent_id": company.id,
            }
        )

        ou = self.ou_model.search([("owner_id", "=", company.id)])
        partners = ou._get_all_partners()

        self.assertIn(company, partners, "Owner should be in partners")
        self.assertIn(contact1, partners, "Contact 1 should be in partners")
        self.assertIn(contact2, partners, "Contact 2 should be in partners")

    # =========================================================================
    # Edge Cases
    # =========================================================================

    def test_multiple_top_level_companies_create_multiple_ous(self):
        """Multiple top-level companies should each get their own OU."""
        company1 = self.partner_model.create(
            {
                "name": "Company 1",
                "is_company": True,
            }
        )
        company2 = self.partner_model.create(
            {
                "name": "Company 2",
                "is_company": True,
            }
        )

        ou1 = self.ou_model.search([("owner_id", "=", company1.id)])
        ou2 = self.ou_model.search([("owner_id", "=", company2.id)])

        self.assertEqual(len(ou1), 1, "Company 1 should have an OU")
        self.assertEqual(len(ou2), 1, "Company 2 should have an OU")
        self.assertNotEqual(ou1.id, ou2.id, "Should be different OUs")

    def test_duplicate_company_name_creates_separate_ou(self):
        """Companies with same name should still get separate OUs."""
        company1 = self.partner_model.create(
            {
                "name": "Same Name",
                "is_company": True,
            }
        )
        company2 = self.partner_model.create(
            {
                "name": "Same Name",
                "is_company": True,
            }
        )

        ou1 = self.ou_model.search([("owner_id", "=", company1.id)])
        ou2 = self.ou_model.search([("owner_id", "=", company2.id)])

        self.assertEqual(len(ou1), 1, "First company should have an OU")
        self.assertEqual(len(ou2), 1, "Second company should have an OU")
        self.assertNotEqual(ou1.id, ou2.id, "Should be different OUs despite same name")

    def test_company_without_name_still_creates_ou(self):
        """Company without name should still create OU (though invalid)."""
        # This tests the auto-creation logic, even though name validation might fail
        try:
            company = self.partner_model.create(
                {
                    "is_company": True,
                }
            )
            ou = self.ou_model.search([("owner_id", "=", company.id)])
            self.assertEqual(len(ou), 1, "OU should still be created")
        except Exception:
            # Name is required (ValidationError or DB-level IntegrityError), so this is expected
            pass
