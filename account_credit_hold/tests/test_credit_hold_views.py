# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from ast import literal_eval
from datetime import date, timedelta
from odoo.tests import common, tagged, Form
from odoo.exceptions import UserError
from odoo import Command, fields
import freezegun


@tagged("post_install", "-at_install")
class TestAccountCreditHoldViews(common.TransactionCase):

    def setUp(self):
        super().setUp()

        # Create test partner
        self.partner = self.env["res.partner"].create(
            {
                "name": "Test Customer",
                "is_company": True,
                "customer_rank": 1,
                "email": "test@example.com",
            }
        )

        # Create followup lines
        self._deactivate_followup_lines()
        self.followup_line_hold = self._create_followup_line(
            "Credit Hold Level", 30, True, send_email=True
        )

        # Create overdue invoice
        self._create_overdue_invoice()

    def _deactivate_followup_lines(self):
        self.env["account_followup.followup.line"].search([]).unlink()

    def _create_followup_line(
        self, name: str, delay: int, hold: bool, send_email: bool = True
    ):
        vals = {
            "company_id": self.env.company.id,
            "name": name,
            "delay": delay,
            "account_hold": hold,
            "send_email": send_email,
        }
        return self.env["account_followup.followup.line"].create(vals)

    def _create_overdue_invoice(self):
        """Create an overdue invoice for testing"""
        with freezegun.freeze_time("2025-01-01"):
            invoice = self.env["account.move"].create(
                {
                    "partner_id": self.partner.id,
                    "move_type": "out_invoice",
                    "date": "2025-01-01",
                    "invoice_date": "2025-01-01",
                    "invoice_line_ids": [
                        Command.create(
                            {
                                "name": "Test Invoice",
                                "quantity": 1.0,
                                "price_unit": 1000.0,
                            }
                        )
                    ],
                    "invoice_date_due": "2025-01-15",
                }
            )
            invoice.action_post()

    def test_credit_hold_menu_action_exists(self):
        """Test that credit hold menu action exists"""
        action = self.env.ref("account_credit_hold.action_res_partner_credit_hold")
        self.assertIsNotNone(action)
        self.assertEqual(action.name, "Credit Hold Management")
        self.assertEqual(action.res_model, "res.partner")

    def test_credit_hold_kanban_view_exists(self):
        """Test that credit hold kanban view exists"""
        view = self.env.ref("account_credit_hold.res_partner_view_kanban_credit_hold")
        self.assertIsNotNone(view)
        self.assertEqual(view.type, "kanban")
        self.assertEqual(view.model, "res.partner")

    def test_credit_hold_list_view_exists(self):
        """Test that credit hold list view exists"""
        view = self.env.ref("account_credit_hold.res_partner_view_tree_credit_hold")
        self.assertIsNotNone(view)
        # Odoo 18 renamed the "tree" view type to "list".
        self.assertEqual(view.type, "list")
        self.assertEqual(view.model, "res.partner")

    def test_credit_hold_search_view_exists(self):
        """Test that credit hold search view exists"""
        view = self.env.ref("account_credit_hold.res_partner_view_search_credit_hold")
        self.assertIsNotNone(view)
        self.assertEqual(view.type, "search")
        self.assertEqual(view.model, "res.partner")

    def test_credit_hold_menu_exists(self):
        """Test that credit hold menu exists"""
        menu = self.env.ref("account_credit_hold.menu_credit_hold_management")
        self.assertIsNotNone(menu)
        self.assertEqual(menu.name, "Credit Hold")
        self.assertEqual(menu.action, self.env.ref("account_credit_hold.action_res_partner_credit_hold"))

    def test_partner_form_shows_credit_hold_ribbon(self):
        """Test that partner form shows credit hold ribbon when on hold"""
        # Place partner on credit hold
        self.partner.action_credit_hold()
        self.assertTrue(self.partner.on_hold)

        # Get form view
        view = self.env.ref("account_credit_hold.res_partner_form_inherit")
        self.assertIsNotNone(view)
        self.assertEqual(view.model, "res.partner")

        # Check that ribbon is in the view
        arch = view.arch
        self.assertIn("web_ribbon", arch)
        self.assertIn("Credit Hold", arch)

    def test_partner_form_shows_postpone_hold_field(self):
        """Test that partner form shows postpone hold field"""
        # Get property form view
        view = self.env.ref("account_credit_hold.view_partner_property_form_inherit")
        self.assertIsNotNone(view)
        self.assertEqual(view.model, "res.partner")

        # Check that postpone hold field is in the view
        arch = view.arch
        self.assertIn("postpone_hold_until", arch)
        self.assertIn("Credit Hold", arch)

    def test_credit_hold_report_action_exists(self):
        """Test that credit hold report action exists"""
        action = self.env.ref("account_credit_hold.account_credit_hold_report_action")
        self.assertIsNotNone(action)
        self.assertEqual(action.name, "Credit Hold Report")
        self.assertEqual(action.report_type, "qweb-pdf")

    def test_credit_hold_report_template_exists(self):
        """Test that credit hold report template exists"""
        template = self.env.ref("account_credit_hold.credit_hold_report")
        self.assertIsNotNone(template)

    def test_credit_hold_server_action_exists(self):
        """Test that credit hold server action exists"""
        action = self.env.ref("account_credit_hold.action_credit_hold")
        self.assertIsNotNone(action)
        self.assertEqual(action.name, "action_credit_hold")
        self.assertEqual(action.state, "code")

    def test_credit_hold_search_filters(self):
        """Test that credit hold search filters work correctly"""
        # Create multiple partners with different states
        partner_on_hold = self.env["res.partner"].create({
            "name": "Customer On Hold",
            "is_company": True,
            "customer_rank": 1,
        })
        partner_on_hold.action_credit_hold()

        partner_not_hold = self.env["res.partner"].create({
            "name": "Customer Not Hold",
            "is_company": True,
            "customer_rank": 1,
        })

        # Test "On Credit Hold" filter
        domain_on_hold = [('on_hold', '=', True)]
        partners_on_hold = self.env["res.partner"].search(domain_on_hold)
        self.assertIn(partner_on_hold, partners_on_hold)
        self.assertNotIn(partner_not_hold, partners_on_hold)

        # Test customers only
        domain_customers = [('customer_rank', '>', 0)]
        partners_customers = self.env["res.partner"].search(domain_customers)
        self.assertIn(self.partner, partners_customers)
        self.assertIn(partner_on_hold, partners_customers)
        self.assertIn(partner_not_hold, partners_customers)

    def test_credit_hold_kanban_view_fields(self):
        """Test that kanban view contains required fields"""
        view = self.env.ref("account_credit_hold.res_partner_view_kanban_credit_hold")
        arch = view.arch

        # Check for required fields in kanban view
        required_fields = ["name", "email", "on_hold", "postpone_hold_until", "total_due"]
        for field in required_fields:
            self.assertIn(field, arch, f"Field '{field}' should be in kanban view")

        # Check for action buttons
        self.assertIn("action_lift_credit_hold", arch)
        self.assertIn("action_credit_hold", arch)

    def test_credit_hold_list_view_fields(self):
        """Test that list view contains required fields"""
        view = self.env.ref("account_credit_hold.res_partner_view_tree_credit_hold")
        arch = view.arch

        # Check for required fields in list view
        required_fields = ["name", "email", "phone", "followup_status", "total_due"]
        for field in required_fields:
            self.assertIn(field, arch, f"Field '{field}' should be in list view")

        # Check for action buttons
        self.assertIn("action_lift_credit_hold", arch)
        self.assertIn("action_credit_hold", arch)

    def test_credit_hold_search_view_filters(self):
        """Test that search view contains required filters"""
        view = self.env.ref("account_credit_hold.res_partner_view_search_credit_hold")
        arch = view.arch

        # Check for required filters
        required_filters = ["on_hold", "hold_postponed", "in_need_of_action", "overdue"]
        for filter_name in required_filters:
            self.assertIn(filter_name, arch, f"Filter '{filter_name}' should be in search view")

        # Check for group by options
        self.assertIn("group_followup_status", arch)
        self.assertIn("group_followup_line", arch)

    def test_followup_line_view_contains_account_hold(self):
        """Test that followup line view contains account hold field"""
        view = self.env.ref("account_credit_hold.account_followup_followup_line_form_inherit")
        arch = view.arch

        # Check for account_hold field
        self.assertIn("account_hold", arch)

        # Check that attach_credit_hold_report field is hidden
        self.assertIn("attach_credit_hold_report", arch)
        self.assertIn('invisible="1"', arch)

    def test_manual_reminder_view_shows_credit_hold_warning(self):
        """Test that manual reminder view shows credit hold warning"""
        view = self.env.ref("account_credit_hold.manual_reminder_view_form_inherit")
        arch = view.arch

        # Check for credit hold warning
        self.assertIn("Credit Hold:", arch)
        self.assertIn("alert alert-warning", arch)
        self.assertIn("partner_id.on_hold", arch)

    def test_credit_hold_action_domain(self):
        """Test that credit hold action has correct domain"""
        action = self.env.ref("account_credit_hold.action_res_partner_credit_hold")

        # ``domain`` and ``context`` are stored as their literal source text,
        # so compare the evaluated value rather than the raw string.
        self.assertEqual(
            literal_eval(action.domain), [('customer_rank', '>', 0)]
        )
        self.assertEqual(
            literal_eval(action.context), {'default_customer_rank': 1}
        )

    def test_credit_hold_action_groups(self):
        """Test that credit hold action has correct groups"""
        action = self.env.ref("account_credit_hold.action_res_partner_credit_hold")

        # Check that accounting groups have access
        group_ids = action.groups_id
        account_manager_group = self.env.ref("account.group_account_manager")
        account_user_group = self.env.ref("account.group_account_user")

        self.assertIn(account_manager_group, group_ids)
        self.assertIn(account_user_group, group_ids)

    def test_credit_hold_menu_sequence(self):
        """Test that credit hold menu has correct sequence"""
        menu = self.env.ref("account_credit_hold.menu_credit_hold_management")
        self.assertEqual(menu.sequence, 55)

    def test_credit_hold_menu_parent(self):
        """Test that credit hold menu has correct parent"""
        menu = self.env.ref("account_credit_hold.menu_credit_hold_management")
        parent_menu = self.env.ref("account.menu_finance_receivables")
        self.assertEqual(menu.parent_id, parent_menu)
