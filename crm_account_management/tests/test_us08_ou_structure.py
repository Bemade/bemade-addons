from odoo.tests import tagged
from odoo.exceptions import ValidationError
from datetime import date
from dateutil.relativedelta import relativedelta

from odoo.fields import Command

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestUS08OUStructure(AccountTestInvoicingCommon):
    """
    US-08: View OU Structure
    
    As a salesperson, I want to see the full structure of an OU (child OUs, member partners), 
    so I can understand the organization.
    
    Acceptance Criteria:
    - OU form shows child OUs (hierarchy)
    - OU form shows member partners (contacts, addresses)
    - Shows owning partner if applicable
    - Can navigate to child OUs and member partners
    
    Requirements Covered:
    - Req 4: Hierarchical accounts (parent_id, child_ids)
    - Req 9: Aggregation from all partners (recursive via _get_all_partners)
    - Req 11: Explicit membership (contacts/addresses can be explicitly added)
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        group_sale = cls.env.ref("sales_team.group_sale_salesman")
        cls.env.user.groups_id = [Command.link(group_sale.id)]
        cls.partner_model = cls.env["res.partner"]
        cls.ou_model = cls.env["organizational.unit"]

    # =========================================================================
    # OU Hierarchy
    # AC: OU form shows child OUs (hierarchy)
    # =========================================================================

    def test_ou_with_parent_no_owner_is_valid(self):
        """OU with parent but no owner is valid (sub-group)."""
        partner = self.partner_model.create(
            {
                "name": "Test Company",
                "is_company": True,
            }
        )
        parent_ou = self.ou_model.search([("owner_id", "=", partner.id)])

        child_ou = self.ou_model.create(
            {
                "name": "Department A",
                "parent_id": parent_ou.id,
            }
        )
        self.assertTrue(child_ou.id, "Sub-OU with parent should be created")

    def test_ou_no_recursive_hierarchy(self):
        """OU cannot be its own parent (recursion check)."""
        partner = self.partner_model.create(
            {
                "name": "Test Company",
                "is_company": True,
            }
        )
        ou = self.ou_model.search([("owner_id", "=", partner.id)])

        with self.assertRaises(ValidationError):
            ou.write({"parent_id": ou.id})

    def test_child_ous_displayed_on_form(self):
        """Child OUs should be accessible via child_ids field."""
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

        self.assertIn(child_ou, parent_ou.child_ids, "Child OU should be in parent's child_ids")

    # =========================================================================
    # Partner Aggregation
    # AC: OU form shows member partners (contacts, addresses)
    # AC: Shows owning partner if applicable
    # =========================================================================

    def test_get_all_partners_includes_owner_and_children(self):
        """_get_all_partners should include owner and its child contacts."""
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

    def test_get_all_partners_includes_explicit_members(self):
        """_get_all_partners should include explicit members."""
        company = self.partner_model.create(
            {
                "name": "Test Company",
                "is_company": True,
            }
        )
        external_contact = self.partner_model.create(
            {
                "name": "External Contact",
            }
        )

        ou = self.ou_model.search([("owner_id", "=", company.id)])
        ou.write({"member_ids": [(4, external_contact.id)]})

        partners = ou._get_all_partners()
        self.assertIn(
            external_contact, partners, "Explicit member should be in partners"
        )

    def test_get_all_partners_recursive_child_ous(self):
        """_get_all_partners should recursively include partners from child OUs."""
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

        partners = parent_ou._get_all_partners()
        self.assertIn(parent_company, partners, "Parent company should be in partners")
        self.assertIn(
            child_company, partners, "Child company should be in partners via child OU"
        )

    # =========================================================================
    # Navigation
    # AC: Can navigate to child OUs and member partners
    # =========================================================================

    def test_ou_shows_owner_partner(self):
        """OU should display its owning partner."""
        company = self.partner_model.create(
            {
                "name": "Test Company",
                "is_company": True,
            }
        )
        ou = self.ou_model.search([("owner_id", "=", company.id)])

        self.assertEqual(ou.owner_id, company, "OU should show owning partner")

    def test_ou_shows_explicit_members(self):
        """OU should display explicit member partners."""
        company = self.partner_model.create(
            {
                "name": "Test Company",
                "is_company": True,
            }
        )
        external_contact = self.partner_model.create(
            {
                "name": "External Contact",
            }
        )

        ou = self.ou_model.search([("owner_id", "=", company.id)])
        ou.write({"member_ids": [(4, external_contact.id)]})

        self.assertIn(external_contact, ou.member_ids, "OU should show explicit members")

    # =========================================================================
    # Constraints
    # Req 4: Hierarchical accounts must be valid
    # =========================================================================

    def test_ou_requires_owner_or_parent(self):
        """OU must have either an owner or a parent OU."""
        # Create a valid OU first, then try to remove both owner and parent
        partner = self.partner_model.create(
            {
                "name": "Test Company",
                "is_company": True,
            }
        )
        ou = self.ou_model.search([("owner_id", "=", partner.id)])

        with self.assertRaises(ValidationError):
            ou.write(
                {
                    "owner_id": False,
                    "parent_id": False,
                }
            )

    # =========================================================================
    # Edge Cases: Sub-OUs without direct partners
    # Supports US-06 (deferred): Create Sub-OUs Within an OU
    # Validates that sub-OUs can exist and metrics handle empty partner sets
    # =========================================================================

    def test_ou_without_owner_metrics_zero(self):
        """OU without owner should have zero metrics."""
        # Create parent OU first
        parent_company = self.partner_model.create(
            {
                "name": "Parent Company",
                "is_company": True,
            }
        )
        parent_ou = self.ou_model.search([("owner_id", "=", parent_company.id)])

        # Create child OU without owner (sub-group)
        child_ou = self.ou_model.create(
            {
                "name": "Department A",
                "parent_id": parent_ou.id,
                "owner_id": False,
            }
        )

        # Metrics should be zero since no partners directly
        self.assertEqual(child_ou.ytd_sales, 0.0)
        self.assertEqual(child_ou.open_quotations_count, 0)
        self.assertEqual(child_ou.open_orders_count, 0)
        self.assertEqual(child_ou.open_opportunities_count, 0)
