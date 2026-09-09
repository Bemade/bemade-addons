from odoo.tests import tagged

from odoo.fields import Command

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestUS09PartnerOUs(AccountTestInvoicingCommon):
    """
    US-09: View Partner's OUs

    As a salesperson, I want to see which OUs a partner belongs to, so I can navigate to the account view.

    Acceptance Criteria:
    - Partner form shows the OU it owns (if top-level company)
    - Partner form shows OUs it is a member of (if contact/address)
    - Can click through to OU form/dashboard

    Requirements Covered:
    - Partner-OU navigation and relationship visibility
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        group_sale = cls.env.ref("sales_team.group_sale_salesman")
        cls.env.user.groups_id = [Command.link(group_sale.id)]
        cls.partner_model = cls.env["res.partner"]
        cls.ou_model = cls.env["organizational.unit"]

    # =========================================================================
    # Partner OU Ownership
    # AC: Partner form shows the OU it owns (if top-level company)
    # =========================================================================

    def test_partner_owned_organizational_unit_ids(self):
        """Partner should have owned_organizational_unit_ids for owned OU."""
        company = self.partner_model.create(
            {
                "name": "Test Company",
                "is_company": True,
            }
        )
        ou = self.ou_model.search([("owner_id", "=", company.id)])

        self.assertEqual(
            company.owned_organizational_unit_ids, ou,
            "Partner should reference its owned OU via One2many",
        )

    def test_partner_action_view_organizational_unit(self):
        """action_view_organizational_unit should return action to open OU form."""
        company = self.partner_model.create(
            {
                "name": "Test Company",
                "is_company": True,
            }
        )
        ou = self.ou_model.search([("owner_id", "=", company.id)])

        action = company.action_view_organizational_unit()
        self.assertEqual(action["res_model"], "organizational.unit")
        self.assertEqual(action["res_id"], ou.id)

    def test_partner_without_ou_action_closes(self):
        """action_view_organizational_unit should close if no OU exists."""
        contact = self.partner_model.create(
            {
                "name": "Standalone Contact",
                "is_company": False,
            }
        )
        action = contact.action_view_organizational_unit()
        self.assertEqual(action["type"], "ir.actions.act_window_close")

    # =========================================================================
    # Name and User Synchronization
    # =========================================================================

    def test_partner_name_change_syncs_to_ou(self):
        """When partner name changes, OU name should sync."""
        company = self.partner_model.create(
            {
                "name": "Original Name",
                "is_company": True,
            }
        )
        ou = self.ou_model.search([("owner_id", "=", company.id)])
        self.assertEqual(ou.name, "Original Name")

        company.write({"name": "New Name"})
        self.assertEqual(ou.name, "New Name", "OU name should sync with partner name")

    def test_partner_user_change_syncs_to_ou(self):
        """When partner user_id changes and OU has single company, sync account manager."""
        user = self.env["res.users"].create(
            {
                "name": "New Sales Rep",
                "login": "newsalesrep@test.com",
            }
        )
        company = self.partner_model.create(
            {
                "name": "Test Company",
                "is_company": True,
            }
        )
        ou = self.ou_model.search([("owner_id", "=", company.id)])

        company.write({"user_id": user.id})
        self.assertEqual(
            ou.user_id, user, "OU account manager should sync from partner"
        )

    # =========================================================================
    # Edge Cases
    # =========================================================================

    def test_contact_without_company_no_ou(self):
        """Contacts without company should not own any OU."""
        contact = self.partner_model.create(
            {
                "name": "Individual Contact",
                "is_company": False,
            }
        )

        self.assertFalse(
            contact.owned_organizational_unit_ids,
            "Contact should not own any OU",
        )

    def test_child_company_no_ou(self):
        """Child companies should not auto-create an OU."""
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

        self.assertFalse(
            child.owned_organizational_unit_ids,
            "Child company should not own any OU",
        )
