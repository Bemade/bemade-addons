# Copyright 2025 Bemade Inc.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo.tests import common, Form
from odoo.exceptions import AccessError


class TestMailFromAddress(common.TransactionCase):
    """Test MailFromAddress model functionality."""

    def setUp(self):
        super().setUp()
        self.MailFromAddress = self.env['mail.from.address']
        self.user_admin = self.env.ref('base.user_admin')
        self.user_demo = self.env.ref('base.user_demo')

    def test_create_from_address(self):
        """Test creating a From address."""
        from_addr = self.MailFromAddress.create({
            'name': 'Customer Service',
            'email': 'support@test.com',
        })
        self.assertEqual(from_addr.name, 'Customer Service')
        self.assertEqual(from_addr.email, 'support@test.com')
        self.assertTrue(from_addr.active)

    def test_display_name_computation(self):
        """Test that display_name is computed correctly (Odoo 18+ style)."""
        from_addr = self.MailFromAddress.create({
            'name': 'Sales',
            'email': 'sales@example.com',
        })
        self.assertEqual(from_addr.display_name, 'Sales <sales@example.com>')

    def test_email_unique_per_company(self):
        """Test that email addresses are unique per company."""
        self.MailFromAddress.create({
            'name': 'Support 1',
            'email': 'support@company1.com',
        })
        # Same email should be allowed for a different company
        company2 = self.env['res.company'].create({'name': 'Company 2'})
        from_addr2 = self.MailFromAddress.create({
            'name': 'Support 2',
            'email': 'support@company1.com',
            'company_id': company2.id,
        })
        self.assertEqual(from_addr2.email, 'support@company1.com')
        # Same email same company should fail
        with self.assertRaises(Exception):
            self.MailFromAddress.create({
                'name': 'Support 3',
                'email': 'support@company1.com',
            })

    def test_get_allowed_addresses_no_restriction(self):
        """Test that addresses with no user restriction are available to all."""
        from_addr = self.MailFromAddress.create({
            'name': 'General',
            'email': 'general@test.com',
            'user_ids': False,  # No restriction
        })
        # Should be available to any user
        allowed = self.MailFromAddress._get_allowed_addresses(user=self.user_admin)
        self.assertIn(from_addr, allowed)
        allowed = self.MailFromAddress._get_allowed_addresses(user=self.user_demo)
        self.assertIn(from_addr, allowed)

    def test_get_allowed_addresses_user_restriction(self):
        """Test that addresses with user restriction work correctly."""
        from_addr = self.MailFromAddress.create({
            'name': 'Restricted',
            'email': 'restricted@test.com',
            'user_ids': [(6, 0, [self.user_admin.id])],
        })
        # Should be available to admin
        allowed = self.MailFromAddress._get_allowed_addresses(user=self.user_admin)
        self.assertIn(from_addr, allowed)
        # Should NOT be available to demo user
        allowed = self.MailFromAddress._get_allowed_addresses(user=self.user_demo)
        self.assertNotIn(from_addr, allowed)

    def test_get_allowed_addresses_inactive(self):
        """Test that inactive addresses are not returned."""
        from_addr = self.MailFromAddress.create({
            'name': 'Inactive',
            'email': 'inactive@test.com',
            'active': False,
        })
        allowed = self.MailFromAddress._get_allowed_addresses(user=self.user_admin)
        self.assertNotIn(from_addr, allowed)

    def test_sequence_ordering(self):
        """Test that addresses are ordered by sequence."""
        addr1 = self.MailFromAddress.create({
            'name': 'Second',
            'email': 'second@test.com',
            'sequence': 20,
        })
        addr2 = self.MailFromAddress.create({
            'name': 'First',
            'email': 'first@test.com',
            'sequence': 10,
        })
        addresses = self.MailFromAddress.search([])
        # Should be ordered by sequence
        self.assertEqual(addresses[0].name, 'First')
        self.assertEqual(addresses[1].name, 'Second')