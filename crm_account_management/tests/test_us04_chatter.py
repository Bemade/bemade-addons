from odoo.tests import tagged
from odoo.exceptions import ValidationError
from datetime import date
from dateutil.relativedelta import relativedelta

from odoo.fields import Command

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestUS04AccountLevelChatter(AccountTestInvoicingCommon):
    """
    US-04: Account-Level Chatter
    
    As a salesperson, I want a chatter/notes section on the customer account, so I can record 
    account-level notes and communications that aren't specific to a single contact.
    
    Acceptance Criteria:
    - Customer account has its own chatter thread
    - Can log notes, schedule activities
    - Chatter is separate from individual partner chatters
    
    Requirements Covered:
    - Req 7: Single-page view (form view with dashboard + chatter)
    - Mail.thread inheritance enables chatter functionality
    - Mail.activity.mixin enables activity scheduling
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

    # =========================================================================
    # Chatter Functionality
    # AC: Customer account has its own chatter thread
    # AC: Can log notes, schedule activities
    # =========================================================================

    def test_ou_inherits_mail_thread(self):
        """Organizational Unit should inherit mail.thread for chatter functionality."""
        company = self.partner_model.create(
            {
                "name": "Test Company",
                "is_company": True,
            }
        )
        ou = self.ou_model.search([("owner_id", "=", company.id)])
        
        # Check that OU has mail.thread attributes
        self.assertTrue(hasattr(ou, 'message_ids'), "OU should have message_ids field")
        self.assertTrue(hasattr(ou, 'message_follower_ids'), "OU should have message_follower_ids field")
        self.assertTrue(hasattr(ou, 'message_partner_ids'), "OU should have message_partner_ids field")

    def test_ou_inherits_mail_activity_mixin(self):
        """Organizational Unit should inherit mail.activity.mixin for activity scheduling."""
        company = self.partner_model.create(
            {
                "name": "Test Company",
                "is_company": True,
            }
        )
        ou = self.ou_model.search([("owner_id", "=", company.id)])
        
        # Check that OU has activity attributes
        self.assertTrue(hasattr(ou, 'activity_ids'), "OU should have activity_ids field")
        self.assertTrue(hasattr(ou, 'activity_state'), "OU should have activity_state field")
        self.assertTrue(hasattr(ou, 'activity_date_deadline'), "OU should have activity_date_deadline field")

    def test_can_post_message_on_ou(self):
        """Should be able to post messages to OU chatter."""
        company = self.partner_model.create(
            {
                "name": "Test Company",
                "is_company": True,
            }
        )
        ou = self.ou_model.search([("owner_id", "=", company.id)])
        
        # Post a message
        message = ou.message_post(
            body="Test message for customer account",
            message_type="comment",
            subtype_xmlid="mail.mt_comment"
        )
        
        self.assertTrue(message.id, "Message should be created")
        self.assertIn(message, ou.message_ids, "Message should be in OU's messages")

    def test_can_create_activity_on_ou(self):
        """Should be able to create activities on OU."""
        company = self.partner_model.create(
            {
                "name": "Test Company",
                "is_company": True,
            }
        )
        ou = self.ou_model.search([("owner_id", "=", company.id)])
        
        # Create an activity
        activity = self.env["mail.activity"].create(
            {
                "res_id": ou.id,
                "res_model": "organizational.unit",
                "res_model_id": self.env["ir.model"]._get("organizational.unit").id,
                "activity_type_id": self.env.ref("mail.mail_activity_data_call").id,
                "summary": "Call customer account",
                "date_deadline": date.today() + relativedelta(days=7),
            }
        )
        
        self.assertTrue(activity.id, "Activity should be created")
        self.assertIn(activity, ou.activity_ids, "Activity should be in OU's activities")

    def test_ou_chatter_separate_from_partner_chatter(self):
        """OU chatter should be separate from partner chatter."""
        company = self.partner_model.create(
            {
                "name": "Test Company",
                "is_company": True,
            }
        )
        ou = self.ou_model.search([("owner_id", "=", company.id)])
        
        # Post message to OU
        ou_message = ou.message_post(
            body="OU level message",
            message_type="comment",
            subtype_xmlid="mail.mt_comment"
        )
        
        # Post message to partner
        partner_message = company.message_post(
            body="Partner level message",
            message_type="comment",
            subtype_xmlid="mail.mt_comment"
        )
        
        # Messages should be separate
        self.assertNotIn(ou_message, company.message_ids, "OU message should not be in partner messages")
        self.assertNotIn(partner_message, ou.message_ids, "Partner message should not be in OU messages")

    def test_can_schedule_meeting_activity(self):
        """Should be able to schedule meeting activities on OU."""
        company = self.partner_model.create(
            {
                "name": "Test Company",
                "is_company": True,
            }
        )
        ou = self.ou_model.search([("owner_id", "=", company.id)])
        
        # Create a meeting activity
        activity = self.env["mail.activity"].create(
            {
                "res_id": ou.id,
                "res_model": "organizational.unit",
                "res_model_id": self.env["ir.model"]._get("organizational.unit").id,
                "activity_type_id": self.env.ref("mail.mail_activity_data_meeting").id,
                "summary": "Quarterly business review",
                "date_deadline": date.today() + relativedelta(days=14),
            }
        )
        
        self.assertTrue(activity.id, "Meeting activity should be created")
        self.assertEqual(activity.activity_type_id.name, "Meeting", "Should be a meeting activity")

    def test_can_log_note_activity(self):
        """Should be able to log note activities on OU."""
        company = self.partner_model.create(
            {
                "name": "Test Company",
                "is_company": True,
            }
        )
        ou = self.ou_model.search([("owner_id", "=", company.id)])
        
        # Create a note activity
        activity = self.env["mail.activity"].create(
            {
                "res_id": ou.id,
                "res_model": "organizational.unit",
                "res_model_id": self.env["ir.model"]._get("organizational.unit").id,
                "activity_type_id": self.env.ref("mail.mail_activity_data_todo").id,
                "summary": "Follow up on pricing discussion",
                "date_deadline": date.today() + relativedelta(days=3),
            }
        )
        
        self.assertTrue(activity.id, "Todo activity should be created")
        self.assertEqual(activity.activity_type_id.name, "To-Do", "Should be a todo activity")

    # =========================================================================
    # Activity State Management
    # =========================================================================

    def test_activity_state_calculation(self):
        """OU activity state should be calculated correctly."""
        company = self.partner_model.create(
            {
                "name": "Test Company",
                "is_company": True,
            }
        )
        ou = self.ou_model.search([("owner_id", "=", company.id)])
        
        # Initially should have no activities
        self.assertFalse(ou.activity_state, "No activities should have no state")
        
        # Create an overdue activity
        past_date = date.today() - relativedelta(days=1)
        self.env["mail.activity"].create(
            {
                "res_id": ou.id,
                "res_model": "organizational.unit",
                "res_model_id": self.env["ir.model"]._get("organizational.unit").id,
                "activity_type_id": self.env.ref("mail.mail_activity_data_call").id,
                "summary": "Overdue call",
                "date_deadline": past_date,
            }
        )
        
        ou.invalidate_recordset()
        self.assertEqual(ou.activity_state, "overdue", "Overdue activity should show as overdue")
        
        # Create a future activity
        future_date = date.today() + relativedelta(days=7)
        self.env["mail.activity"].create(
            {
                "res_id": ou.id,
                "res_model": "organizational.unit",
                "res_model_id": self.env["ir.model"]._get("organizational.unit").id,
                "activity_type_id": self.env.ref("mail.mail_activity_data_call").id,
                "summary": "Future call",
                "date_deadline": future_date,
            }
        )
        
        ou.invalidate_recordset()
        self.assertEqual(ou.activity_state, "overdue", "With overdue activity, state should remain overdue")

    def test_activity_date_deadline_calculation(self):
        """OU activity date deadline should be calculated correctly."""
        company = self.partner_model.create(
            {
                "name": "Test Company",
                "is_company": True,
            }
        )
        ou = self.ou_model.search([("owner_id", "=", company.id)])
        
        # Initially should have no deadline
        self.assertFalse(ou.activity_date_deadline, "No activities should have no deadline")
        
        # Create activities with different deadlines
        past_date = date.today() - relativedelta(days=5)
        today_date = date.today()
        future_date = date.today() + relativedelta(days=10)
        
        for deadline in [past_date, today_date, future_date]:
            self.env["mail.activity"].create(
                {
                    "res_id": ou.id,
                    "res_model": "organizational.unit",
                "res_model_id": self.env["ir.model"]._get("organizational.unit").id,
                    "activity_type_id": self.env.ref("mail.mail_activity_data_call").id,
                    "summary": f"Call on {deadline}",
                    "date_deadline": deadline,
                }
            )
        
        ou.invalidate_recordset()
        self.assertEqual(ou.activity_date_deadline, past_date, "Should return earliest deadline")

    # =========================================================================
    # Message Followers
    # =========================================================================

    def test_can_add_followers_to_ou(self):
        """Should be able to add followers to OU chatter."""
        company = self.partner_model.create(
            {
                "name": "Test Company",
                "is_company": True,
            }
        )
        ou = self.ou_model.search([("owner_id", "=", company.id)])
        
        # Create a user to follow
        user = self.env["res.users"].create(
            {
                "name": "Test User",
                "login": "testuser@example.com",
            }
        )
        
        # Add follower
        ou.message_subscribe(partner_ids=[user.partner_id.id])
        
        self.assertIn(user.partner_id, ou.message_partner_ids, "User should be following OU")

    def test_ou_account_manager_auto_follows(self):
        """OU account manager should automatically follow the OU."""
        user = self.env["res.users"].create(
            {
                "name": "Sales Rep",
                "login": "salesrep@example.com",
            }
        )
        
        company = self.partner_model.create(
            {
                "name": "Test Company",
                "is_company": True,
                "user_id": user.id,
            }
        )
        ou = self.ou_model.search([("owner_id", "=", company.id)])
        
        # Account manager should be following
        self.assertIn(user.partner_id, ou.message_partner_ids, "Account manager should follow OU")
