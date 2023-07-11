from .test_task_template import TestTaskTemplateCommon
from odoo.tests.common import tagged, HttpCase


@tagged("-at_install", "post_install")
class TestSalesOrder(TestTaskTemplateCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({
            'name': 'Test Partner',
        })
        cls.equipment =cls.env['bemade_fsm.equipment'].create({
            'name': 'test equipment',
            'partner_location_id': cls.partner.id,
        })
        cls.so_equipment = cls.env['bemade_fsm.equipment'].create({
            'name': 'test equipment 2',
            'partner_location_id': cls.partner.id,
        })
        cls.sale_order1 = cls.env['sale.order'].create({
            'partner_id': cls.partner.id,
            'client_order_ref': 'TEST ORDER 1',
            'state': 'draft',
            'equipment_id': cls.so_equipment.id,
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
            'client_order_ref': 'TEST ORDER 2',
            'state': 'draft',
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

    def test_order_confirmation_equipment(self):
        so = self.sale_order1
        self.assertEqual(so.equipment_id, so.equipment_id)
        self.assertFalse(so.order_line[0].product_id.task_template_id.equipment_id)
        so.action_confirm()
        task = so.order_line.filtered(lambda l: not l.product_id.task_template_id.equipment_id).task_id
        self.assertEqual(task.equipment_id, self.so_equipment)

    def test_task_template_with_equipment_flow(self):
        so = self.sale_order1
        self.product_task_global_project.task_template_id.equipment_id = self.equipment
        so.action_confirm()
        task = so.order_line.filtered(lambda l: l.product_id.task_template_id.equipment_id).task_id
        self.assertEqual(task.equipment_id, self.equipment)

    def test_task_mark_done(self):
        so = self.sale_order2
        so.action_confirm()
        sol = so.order_line[0]
        parent_task = sol.task_id
        child_task = parent_task.child_ids[0]
        # Marking the top-level tasks done should set the delivered quantity to some non-zero value based on the UOM
        parent_task.action_fsm_validate()
        # sol._compute_qty_delivered()
        self.assertTrue(sol.qty_delivered != 0)
        # Marking a child task done should not create a sale order
        child_task.action_fsm_validate()
        self.assertFalse(child_task.sale_order_id)


@tagged("-at_install", "post_install", "slow")
class TestSaleOrderTour(HttpCase, TestSalesOrder):
    def test_sale_order_tour_no_invoice_button_for_non_manager(self):
        # Make sure a non-manager cannot mark a task as ready to invoice
        so = self.sale_order2
        so.action_confirm()
        with self.assertRaises(AssertionError) as e:
            self.start_tour('/web', 'sale_order_tour',
                            login='mruser', )
        self.assertTrue("Click on the ready to invoice button" in str(e.exception))

    def test_task_mark_to_invoice(self):
        # Make sure that when a manager clicks the ready to invoice button, the qty delivered is updated on the SO
        so = self.sale_order2
        so.action_confirm()
        sol = so.order_line.filtered(lambda l: 'Test Product 3' in l.name)
        self.start_tour('/web', 'sale_order_tour', login='misterpm')
        self.assertTrue(sol.qty_delivered != 0)