from .test_task_template import TestTaskTemplateCommon
from odoo.tests.common import tagged


@tagged("-at_install", "post_install")
class TestTaskTemplateSalesOrder(TestTaskTemplateCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({
            'name': 'Test Partner',
        })
        cls.sale_order1 = cls.env['sale.order'].create({
            'partner_id': cls.partner.id,
            'client_order_ref': 'TEST ORDER',
        })
        cls.sol_serv_order = cls.env['sale.order.line'].create({
            'name': cls.product_task_global_project.name,
            'product_id': cls.product_task_global_project.id,
            'product_uom_qty': 1,
            'product_uom': cls.product_task_global_project.uom_id.id,
            'price_unit': 120.0,
            'order_id': cls.sale_order1.id,
            'tax_id': False,
        })
        cls.sol_serv_order_task_in_project = cls.env['sale.order.line'].create({
            'name': cls.product_task_in_project.name,
            'product_id': cls.product_task_in_project.id,
            'product_uom_qty': 1,
            'product_uom': cls.product_task_in_project.uom_id.id,
            'price_unit': 150.0,
            'order_id': cls.sale_order1.id,
            'tax_id': False,
        })
        cls.sale_order2 = cls.env['sale.order'].create({
            'partner_id': cls.partner.id,
            'client_order_ref': 'TEST ORDER',
        })
        cls.sol_tree_order = cls.env['sale.order.line'].create({
            'name': cls.product_task_tree_global_project.name,
            'product_id': cls.product_task_tree_global_project.id,
            'product_uom_qty': 1,
            'product_uom': cls.product_task_tree_global_project.uom_id.id,
            'price_unit': 120.0,
            'order_id': cls.sale_order2.id,
            'tax_id': False,
        })
        cls.sol_serv_order_task_in_project = cls.env['sale.order.line'].create({
            'name': cls.product_task_tree_in_project.name,
            'product_id': cls.product_task_tree_in_project.id,
            'product_uom_qty': 1,
            'product_uom': cls.product_task_tree_in_project.uom_id.id,
            'price_unit': 150.0,
            'order_id': cls.sale_order2.id,
            'tax_id': False,
        })

    @tagged('-at_install', 'post_install')
    def test_order_confirmation_simple_template(self):
        """ Confirming the order should create a task in the global project. """
        so = self.sale_order1
        so.action_confirm()
        sol1 = so.order_line[0]
        sol2 = so.order_line[1]
        task1 = sol1.task_id
        task2 = sol2.task_id
        self.assertTrue(task1)
        self.assertTrue(task2)
        self.assertTrue(self.task1.name in task1.name)
        self.assertTrue(self.task1.name in task2.name)
        self.assertTrue(self.task1.planned_hours == task1.planned_hours)

    def test_order_confirmation_tree_template(self):
        def assert_structure(sol):
            self.assertTrue(sol.task_id.child_ids and len(sol.task_id.child_ids) == 2)
            self.assertTrue(self.parent_task.name in sol.task_id.name)
            self.assertTrue(self.child_task_1.name in sol.task_id.child_ids[0].name)
            self.assertTrue(self.child_task_2.name in sol.task_id.child_ids[1].name)
            self.assertTrue(sol.task_id.child_ids[1].child_ids and len(sol.task_id.child_ids.child_ids) == 1)
            self.assertTrue(self.grandchild_task.name in sol.task_id.child_ids.child_ids[0].name)
        so = self.sale_order2
        so.action_confirm()
        sol1 = so.order_line[0]
        sol2 = so.order_line[1]
        assert_structure(sol1)
        assert_structure(sol2)
        