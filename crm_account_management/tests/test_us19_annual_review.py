from odoo.tests import tagged
from odoo.exceptions import ValidationError
from datetime import date
from dateutil.relativedelta import relativedelta

from odoo.fields import Command

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged("post_install", "-at_install")
class TestUS19AnnualReview(AccountTestInvoicingCommon):
    """
    US-19: Generate Annual Review Report
    
    As a salesperson, I want to generate a printable annual review report for a customer account, 
    so I can use it in customer meetings.
    
    Acceptance Criteria:
    - PDF report showing: sales summary, YoY comparison, top products, buying trends
    - Can select date range (default: last 12 months)
    - Branded with company logo
    
    Requirements Covered:
    - Annual reporting functionality
    - Data aggregation for reporting
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        group_sale = cls.env.ref("sales_team.group_sale_salesman")
        cls.env.user.groups_id = [Command.link(group_sale.id)]
        cls.partner_model = cls.env["res.partner"]
        cls.ou_model = cls.env["organizational.unit"]

    # =========================================================================
    # Report Generation
    # AC: PDF report showing: sales summary, YoY comparison, top products, buying trends
    # =========================================================================

    def test_action_print_annual_review(self):
        """action_print_annual_review should return report action."""
        company = self.partner_model.create(
            {
                "name": "Test Company",
                "is_company": True,
            }
        )
        ou = self.ou_model.search([("owner_id", "=", company.id)])

        action = ou.action_print_annual_review()
        # report_action returns ir.actions.act_window for preview
        self.assertIn(action["type"], ["ir.actions.report", "ir.actions.act_window"])
