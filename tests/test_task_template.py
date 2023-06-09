from odoo.tests.common import TransactionCase, HttpCase, tagged
from odoo.exceptions import UserError


class TestTaskTemplateCommon(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        user_group_employee = cls.env.ref('base.group_user')
        user_group_project_user = cls.env.ref('project.group_project_user')
        user_group_project_manager = cls.env.ref('project.group_project_manager')
        user_group_sales_manager = cls.env.ref('sales_team.group_sale_manager')
        user_group_sales_user = cls.env.ref('sales_team.group_sale_salesman')
        user_product_customer = cls.env.ref('customer_product_code.group_product_customer_code_user')

        group_ids = [user_group_employee, user_group_project_user, user_group_project_manager, user_group_sales_user,
                     user_group_sales_manager]
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
                                  user_group_sales_user.id])]
        })
        hours_uom = cls.env['uom.uom'].search([('name', '=', 'Hour')]) or False
        # Test product to use with the various tests
        cls.task1 = cls.env['project.task.template'].create({
            'name': 'Template 1',
        })
        cls.project = cls.env['project.project'].create({
            'name': 'Test Project',
        })
        cls.product_task_global_project = cls.env['product.product'].create({
            'name': 'Test Product 1',
            'type': 'service',
            'service_tracking': 'task_global_project',
            'project_id': cls.project.id,
            'task_template_id': cls.task1.id,
            'uom_id': hours_uom.id,
            'uom_po_id': hours_uom.id,
        })
        cls.product_task_in_project = cls.env['product.product'].create({
            'name': 'Test Product 2',
            'type': 'service',
            'service_tracking': 'task_in_project',
            'task_template_id': cls.task1.id,
            'uom_po_id': hours_uom.id,
            'uom_id': hours_uom.id,
        })
        cls.partner = cls.env['res.partner'].create({'name': 'Test Partner'})
        cls.sale_order = cls.env['sale.order'].create({
            'partner_id': cls.partner.id,
            'client_order_ref': 'TEST ORDER',
        })
        cls.sol_serv_order = cls.env['sale.order.line'].create({
            'name': cls.product_task_global_project.name,
            'product_id': cls.product_task_global_project.id,
            'product_uom_qty': 1,
            'product_uom': cls.product_task_global_project.uom_id.id,
            'price_unit': 120.0,
            'order_id': cls.sale_order.id,
            'tax_id': False,
        })


@tagged('-at_install', 'post_install')
class TestTaskTemplate(TestTaskTemplateCommon):

    def test_delete_task_template(self):
        """User should never be able to delete a task template used on a product"""
        with self.assertRaises(UserError):
            self.task1.unlink()

    def test_order_confirmation_single_task(self):
        """ Confirming the order should create a task in the global project. """
        self.sale_order.action_confirm()
        so = self.sale_order
        sol = self.sale_order.order_line[0]
        task = sol.task_id
        self.assertTrue(task)



@tagged('-at_install', 'post_install')
class TestTaskTemplateTour(HttpCase, TestTaskTemplateCommon):

    def test_task_template_tour(self):
        self.start_tour('/web', 'task_template_tour',
                        login='misterpm', )
