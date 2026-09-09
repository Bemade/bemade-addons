# Copyright 2025 Bemade Inc.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo.tests import common, Form
from odoo.tools import mute_logger


class TestMailComposeMessage(common.TransactionCase):
    """Test mail.compose.message From address selection functionality."""

    def setUp(self):
        super().setUp()
        self.MailFromAddress = self.env['mail.from.address']
        self.MailComposeMessage = self.env['mail.compose.message']
        self.partner = self.env['res.partner'].create({
            'name': 'Test Partner',
            'email': 'partner@test.com',
        })
        # Archive all pre-existing From addresses for test isolation
        self.MailFromAddress.search([]).write({'active': False})
        # Create test From addresses
        self.from_addr_1 = self.MailFromAddress.create({
            'name': 'Support',
            'email': 'support@test.com',
            'sequence': 10,
        })
        self.from_addr_2 = self.MailFromAddress.create({
            'name': 'Sales',
            'email': 'sales@test.com',
            'sequence': 20,
        })

    def test_from_address_field_exists(self):
        """Test that from_address_id field is added to composer."""
        compose = self.MailComposeMessage.new({
            'composition_mode': 'comment',
            'model': 'res.partner',
            'res_ids': str(self.partner.id),
        })
        self.assertTrue(hasattr(compose, 'from_address_id'))

    def test_single_from_address_auto_selected(self):
        """Test that a single From address is auto-selected."""
        # Archive one address so only one is available
        self.from_addr_2.active = False
        
        compose = self.MailComposeMessage.with_context(
            default_model='res.partner',
            default_res_ids=[self.partner.id],
            default_composition_mode='comment',
        ).create({})
        
        self.assertEqual(compose.from_address_id, self.from_addr_1)

    def test_multiple_from_addresses_not_auto_selected(self):
        """Test that multiple From addresses are not auto-selected."""
        compose = self.MailComposeMessage.with_context(
            default_model='res.partner',
            default_res_ids=[self.partner.id],
            default_composition_mode='comment',
        ).create({})
        
        # When multiple addresses are available, none should be auto-selected
        self.assertFalse(compose.from_address_id)

    def test_send_mail_uses_from_address_email(self):
        """Test that sending uses the from_address_id email."""
        compose = self.MailComposeMessage.with_context(
            default_model='res.partner',
            default_res_ids=[self.partner.id],
            default_composition_mode='comment',
        ).create({
            'subject': 'Test Subject',
            'body': '<p>Test body</p>',
            'from_address_id': self.from_addr_1.id,
        })
        
        # Call the send method (this will trigger _action_send_mail_comment)
        with mute_logger('odoo.addons.mail.models.mail_thread'):
            compose._action_send_mail_comment([self.partner.id])
        
        # Verify email_from was set correctly
        self.assertEqual(compose.email_from, self.from_addr_1.email)

    def test_from_address_changes_email_from(self):
        """Test that changing from_address_id updates email_from on send."""
        compose = self.MailComposeMessage.with_context(
            default_model='res.partner',
            default_res_ids=[self.partner.id],
            default_composition_mode='comment',
        ).create({
            'subject': 'Test Subject',
            'body': '<p>Test body</p>',
            'from_address_id': self.from_addr_2.id,
        })
        
        with mute_logger('odoo.addons.mail.models.mail_thread'):
            compose._action_send_mail_comment([self.partner.id])
        
        # Verify email_from was set to from_address_2's email
        self.assertEqual(compose.email_from, self.from_addr_2.email)

    def test_from_address_user_restriction(self):
        """Test that user-restricted addresses are properly filtered."""
        # Create a user-restricted address
        user = self.env['res.users'].create({
            'name': 'Test User',
            'login': 'test_user_from',
            'email': 'test_user@test.com',
        })
        restricted_addr = self.MailFromAddress.create({
            'name': 'Restricted',
            'email': 'restricted@test.com',
            'user_ids': [(6, 0, [user.id])],
        })
        
        # Login as this user
        compose = self.MailComposeMessage.with_user(user).with_context(
            default_model='res.partner',
            default_res_ids=[self.partner.id],
            default_composition_mode='comment',
        ).new({})
        
        # The restricted address should be available to this user
        allowed = self.MailFromAddress._get_allowed_addresses(user=user)
        self.assertIn(restricted_addr, allowed)
        # But not to other users
        admin_user = self.env.ref('base.user_admin')
        allowed_admin = self.MailFromAddress._get_allowed_addresses(user=admin_user)
        self.assertNotIn(restricted_addr, allowed_admin)