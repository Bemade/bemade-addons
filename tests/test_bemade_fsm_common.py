from odoo.tests.common import TransactionCase


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

        group_ids = [user_group_employee,
                     user_group_project_user,
                     user_group_project_manager,
                     user_group_fsm_user,
                     user_group_fsm_manager,
                     user_group_sales_user,
                     user_group_sales_manager, ]
        if user_product_customer:
            group_ids.append(user_product_customer)

        # Test user with project access rights for the various tests
        Users = cls.env['res.users'].with_context({'no_reset_password': True})
        cls.user = Users.create({
            'name': 'Project Manager',
            'login': 'misterpm',
            'password': 'misterpm',
            'email': 'mrpm@testco.com',
            'signature': 'Mr. PM',
            'groups_id': [(6, 0, [user_group_employee.id, user_group_project_user.id, user_group_project_manager.id,
                                  user_group_sales_user.id])],
        })
