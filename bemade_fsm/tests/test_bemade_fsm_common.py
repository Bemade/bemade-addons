from odoo.tests.common import TransactionCase, tagged
from odoo import Command


@tagged("-at_install", "post_install")
class FSMManagerUserTransactionCase(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        user_group_employee = cls.env.ref('base.group_user')
        user_group_project_user = cls.env.ref('project.group_project_user')
        user_group_project_manager = cls.env.ref('project.group_project_manager')
        user_group_fsm_user = cls.env.ref('industry_fsm.group_fsm_user')
        user_group_fsm_manager = cls.env.ref('industry_fsm.group_fsm_manager')
        user_group_sales_manager = cls.env.ref('sales_team.group_sale_manager')
        user_group_sales_user = cls.env.ref('sales_team.group_sale_salesman')
        user_product_customer = cls.env.ref('customer_product_code.group_product_customer_code_user')

        group_ids = [user_group_employee.id,
                     user_group_project_user.id,
                     user_group_project_manager.id,
                     user_group_fsm_user.id,
                     user_group_fsm_manager.id,
                     user_group_sales_user.id,
                     user_group_sales_manager.id, ]
        if user_product_customer:
            group_ids.append(user_product_customer.id)

        # Test user with project access rights for the various tests
        Users = cls.env['res.users'].with_context({'no_reset_password': True})
        cls.user = Users.create({
            'name': 'Project Manager',
            'login': 'misterpm',
            'password': 'misterpm',
            'email': 'mrpm@testco.com',
            'signature': 'Mr. PM',
            'groups_id': [Command.set(group_ids)],
        })
        group_ids.remove(user_group_fsm_manager.id)
        group_ids.remove(user_group_project_manager.id)
        cls.user_limited = Users.create({
            'name': 'Project User',
            'login': 'mruser',
            'password': 'mruser',
            'email': 'mruser@testco.com',
            'signature': 'Mr. User',
            'groups_id': [Command.set(group_ids)]
        })
