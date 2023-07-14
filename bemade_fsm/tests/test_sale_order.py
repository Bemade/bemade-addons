from .test_task_template import TestTaskTemplateCommon
from odoo.tests.common import tagged, HttpCase, Form
from odoo import Command


@tagged("-at_install", "post_install")
class TestSalesOrder(TestTaskTemplateCommon):
    @tagged('-at_install', 'post_install')
    def test_order_confirmation_simple_template(self):
        """ Confirming the order should create a task in the global project based on the task template. """
        partner = self._generate_partner()
        so = self._generate_sale_order(partner=partner)
        task_template = self._generate_task_template(planned_hours=8)
        product = self._generate_product(task_template=task_template)
        sol = self._generate_sale_order_line(so, product=product)

        so.action_confirm()

        task = sol.task_id
        self.assertTrue(task)
        self.assertTrue(task_template.name in task.name)
        self.assertTrue(task_template.planned_hours == task.planned_hours)

    def test_order_confirmation_tree_template(self):
        partner = self._generate_partner()
        so = self._generate_sale_order(partner=partner)
        task_template = self._generate_task_template(structure=[2, 1],
                                                     names=['Parent Template', 'Child Template',
                                                            'Grandchild Template'])
        product = self._generate_product(task_template=task_template)
        sol = self._generate_sale_order_line(so, product=product)

        so.action_confirm()

        self.assertTrue(sol.task_id.child_ids and len(sol.task_id.child_ids) == 2)
        self.assertTrue(self.parent_task.name in sol.task_id.name)
        self.assertTrue(self.child_task_1.name in sol.task_id.child_ids[0].name)
        self.assertTrue(self.child_task_2.name in sol.task_id.child_ids[1].name)
        self.assertTrue(sol.task_id.child_ids[0].child_ids and len(sol.task_id.child_ids[0].child_ids) == 1)
        self.assertTrue(self.grandchild_task.name in sol.task_id.child_ids.child_ids[0].name)

    def test_order_confirmation_equipment(self):
        """ The equipment selected on the SO should transfer to the task."""
        partner = self._generate_partner()
        equipment = self._generate_equipment(partner=partner)
        so = self._generate_sale_order(partner=partner, equipment=equipment)
        task_template = self._generate_task_template(planned_hours=8)
        product1 = self._generate_product(task_template=task_template)
        product2 = self._generate_product()
        sol1 = self._generate_sale_order_line(so, product=product1)
        sol2 = self._generate_sale_order_line(so, product=product2)

        so.action_confirm()

        task1 = sol1.task_id
        task2 = sol2.task_id
        self.assertEqual(task1.equipment_ids[0], equipment)
        self.assertEqual(task2.equipment_ids[0], equipment)

    def test_task_template_with_equipment_flow(self):
        """ The equipment selected on a task template should flow down to the task created on SO confirmation."""
        partner = self._generate_partner()
        equipment = self._generate_equipment(partner=partner)
        so = self._generate_sale_order(partner=partner)
        task_template = self._generate_task_template(equipment=equipment)
        product = self._generate_product(task_template=task_template)
        sol = self._generate_sale_order_line(so, product=product)

        so.action_confirm()

        self.assertEqual(sol.task_id.equipment_ids[0], equipment)

    def test_task_mark_done(self):
        """ Marking the task linked to an SO line should mark the line delivered. Marking sub-tasks done should not."""
        partner = self._generate_partner()
        so = self._generate_sale_order(partner=partner)
        task_template = self._generate_task_template(structure=[2], names=["Parent Task", "Subtask"])
        product = self._generate_product(task_template=task_template)
        sol = self._generate_sale_order_line(so, product=product)
        so.action_confirm()
        parent_task = sol.task_id
        subtasks = parent_task._get_all_subtasks()

        # Marking the subtasks done should not increment delivered quantity
        subtasks.action_fsm_validate()
        self.assertEqual(sol.qty_delivered, 0)

        # Marking the top-level tasks done should set the delivered quantity to some non-zero value based on the UOM
        parent_task.action_fsm_validate()
        self.assertTrue(sol.qty_delivered != 0)


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

    def test_task_contacts_through_sale_order(self):
        """ Make sure the site contacts and work order contacts transfer correctly from the SO to the task."""

        partner = self._generate_partner()
        contact1 = self._generate_partner('Site contact', 'person', partner)
        contact2 = self._generate_partner('Work order contact', 'person', partner)
        partner.write({
            'site_contacts': [Command.set([contact1.id])],
            'work_order_contacts': [Command.set([contact2.id])],
        })
        so = self._generate_sale_order(partner)
        product = self._generate_product()
        sol = self._generate_sale_order_line(product=product)

        so.action_confirm()

        self.assertEqual(so.work_order_contacts, partner.work_order_contacts)
        self.assertEqual(so.site_contacts, partner.site_contacts)
        self.assertEqual(sol.task_id.work_order_contacts, partner.work_order_contacts)
        self.assertEqual(sol.task_id.site_contacts, partner.site_contacts)

    def test_changing_task_contacts_mirrors_with_sale_order(self):
        partner = self._generate_partner()
        contact = self._generate_partner("Contact", "person", partner)
        so = self._generate_sale_order(partner)
        product = self._generate_product()
        sol = self._generate_sale_order_line(so, product)
        so.action_confirm()
        task = sol.task_id
        task_form = Form(task)

        # Now change the site/work order contact on the task and make sure it feeds back to the sales order
        task_form.site_contacts.add(contact)
        task_form.work_order_contacts.add(contact)
        task_form.save()

        self.assertEqual(task.site_contacts, so.site_contacts)
        self.assertEqual(task.work_order_contacts, so.work_order_contacts)

        # Test changing it on the SO feeds back to the task as well
        f = Form(so)
        f.work_order_contacts.remove(contact.id)
        f.site_contacts.remove(contact.id)
        f.save()

        self.assertEqual(task.site_contacts, so.site_contacts)
        self.assertEqual(task.work_order_contacts, so.work_order_contacts)
