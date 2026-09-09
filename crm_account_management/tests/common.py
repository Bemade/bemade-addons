from odoo.fields import Command

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


class OUTestCommon(AccountTestInvoicingCommon):
    """Base class for crm_account_management tests."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        group_sale = cls.env.ref("sales_team.group_sale_salesman")
        cls.env.user.groups_id = [Command.link(group_sale.id)]

    def _make_order(self, vals):
        """Create a sale.order."""
        return self.env["sale.order"].create(vals)
