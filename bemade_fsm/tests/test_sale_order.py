from .test_task_template import BemadeFSMBaseTest
from odoo.tests.common import tagged, HttpCase, Form
from odoo import Command


@tagged("-at_install", "post_install")
class TestSalesOrder(BemadeFSMBaseTest):
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

    def test_task_template_tree_order_confirmation(self):
        partner = self._generate_partner()
        so = self._generate_sale_order(partner=partner)
        parent_template = self._generate_task_template(structure=[2, 1],
                                                       names=['Parent Template',
                                                              'Child Template',
                                                              'Grandchild Template'])
        child_template_1 = parent_template.subtasks[0]
        child_template_2 = parent_template.subtasks[1]
        grandchild_template = parent_template.subtasks[0].subtasks[0]
        product = self._generate_product(task_template=parent_template)
        sol = self._generate_sale_order_line(so, product=product)

        so.action_confirm()

        parent = sol.task_id
        c1, c2 = parent.child_ids
        gc = c1.child_ids[:1]
        self.assertTrue(parent.child_ids and len(parent.child_ids) == 2)
        self.assertTrue(parent_template.name in parent.name)
        self.assertEqual(child_template_1.name, c1.name)
        self.assertEqual(child_template_2.name, c2.name)
        self.assertTrue(c1.child_ids and len(c1.child_ids) == 1)
        self.assertEqual(grandchild_template.name, gc.name)

    def test_order_confirmation_single_equipment(self):
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

    def test_order_confirmation_multiple_equipment(self):
        """ All equipment items should flow from the sale order line to the final task """
        partner = self._generate_partner()
        for i in range(5):
            self._generate_equipment(partner=partner)
        sale_order = self._generate_sale_order(
            partner=partner)  # No default equipment since more than 3 on partner
        sol1, sol2, sol3 = [self._generate_sale_order_line(sale_order=sale_order) for i
                            in range(3)]
        sol1.equipment_ids = [
            Command.set([partner.equipment_ids[i].id for i in range(2)])]
        sol3.equipment_ids = [
            Command.set([partner.equipment_ids[i].id for i in range(2, 5)])]

        sale_order.action_confirm()

        self.assertEqual(sol1.equipment_ids, sol1.task_id.equipment_ids)
        self.assertEqual(sol2.equipment_ids, sol2.task_id.equipment_ids)
        self.assertEqual(sol3.equipment_ids, sol3.task_id.equipment_ids)

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

    def test_sale_order_line_gets_default_equipment(self):
        """ Sale order lines created on an SO with default equipment set should inherit that default equipment. """
        partner = self._generate_partner()
        self._generate_equipment(partner=partner)
        sale_order = self._generate_sale_order(partner=partner)

        sol = self._generate_sale_order_line(sale_order=sale_order)

        self.assertEqual(sol.equipment_ids, partner.equipment_ids)

    def test_sale_order_gets_correct_default_equipment_from_partner(self):
        """ Should pick up equipment from the partner."""
        partner = self._generate_partner()
        self._generate_equipment(partner=partner)

        sale_order = self._generate_sale_order(partner=partner)

        self.assertEqual(sale_order.default_equipment_ids, partner.owned_equipment_ids)

    def test_sale_order_default_equipment_maximum_number(self):
        parent = self._generate_partner()
        child = self._generate_partner(parent=parent)
        for i in range(3):
            self._generate_equipment(child)

        sale_order = self._generate_sale_order(partner=parent)

        self.assertEqual(sale_order.default_equipment_ids, parent.owned_equipment_ids)

    def test_sale_order_no_default_equipment_with_more_than_three_owned_on_partner(self):
        parent = self._generate_partner()
        child = self._generate_partner(parent=parent)
        for i in range(4):
            self._generate_equipment(child)

        sale_order = self._generate_sale_order(partner=parent)

        self.assertEqual(sale_order.default_equipment_ids, parent.owned_equipment_ids)

    def test_sale_order_resets_default_equipment_on_partner_change(self):
        partner_1 = self._generate_partner()
        partner_2 = self._generate_partner()
        self._generate_equipment(partner=partner_1)
        sale_order = self._generate_sale_order(partner_1)
        form = Form(sale_order)

        form.partner_id = partner_2
        form.save()

        self.assertFalse(sale_order.default_equipment_ids)

    def test_sale_order_prioritize_shipping_location_equipments(self):
        parent = self._generate_partner()
        child = self._generate_partner(parent=parent, location_type='delivery')
        self._generate_equipment(partner=parent)
        self._generate_equipment(partner=child)

        sale_order = self._generate_sale_order(partner=parent, shipping_location=child)

        self.assertEqual(sale_order.default_equipment_ids, child.equipment_ids)

    def test_default_equipment_transfers_to_sale_order_line(self):
        partner = self._generate_partner()
        for i in range(3):
            self._generate_equipment(partner=partner)
        sale_order = self._generate_sale_order(partner=partner)

        for i in range(3):
            self._generate_sale_order_line(sale_order=sale_order)

        for line in sale_order.order_line:
            self.assertEqual(line.equipment_ids, partner.equipment_ids)

    def test_task_mark_done(self):
        """ Marking the task linked to an SO line should mark the line delivered. Marking sub-tasks done should not."""
        partner = self._generate_partner()
        so = self._generate_sale_order(partner=partner)
        task_template = self._generate_task_template(structure=[2],
                                                     names=["Parent Task", "Subtask"])
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
        sol = self._generate_sale_order_line(sale_order=so, product=product)

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

    def test_tasks_created_at_order_confirmation_have_no_assignees(self):
        so, visit, sol1, sol2 = self._generate_so_with_one_visit_two_lines()
        user = self._generate_project_user(name="User", login='login')

        # We test as a specific user since testing as root may not produce the error
        so.with_user(user).action_confirm()

        visit_task = visit.task_id
        subtask1 = visit_task.child_ids[0]
        subtask2 = visit_task.child_ids[1]
        self.assertFalse(visit_task.user_ids)
        self.assertFalse(subtask1.user_ids)
        self.assertFalse(subtask2.user_ids)
        
    def test_long_line_name_overflows_to_task_description(self):
        so = self._generate_sale_order()
        product = self._generate_product()
        product.description_sale = "This is a long product description.\n" \
                                   "It even spans multiple lines.\n" \
                                   "One could find this annoying in a task name."

        sol = self._generate_sale_order_line(sale_order=so, product=product)

        so.action_confirm()
        task = sol.task_id

        self.assertFalse("This is a long product description." in task.name)
        self.assertFalse("It even spans multiple lines." in task.name)
        self.assertFalse("One could find this annoying in a task name." in task.name)
        self.assertTrue("It even spans multiple lines." in task.description)
        self.assertTrue("One could find this annoying in a task name."
                        in task.description)

    def test_subtask_templates_no_description_if_blank_on_template(self):
        so = self._generate_sale_order()
        template = self._generate_task_template(structure=[5], names=['Parent', 'Child'])
        template.description = ""
        template.subtasks[0].description = "Some fixed description"
        for t in template.subtasks[1:]:
            t.description = ""
        product = self._generate_product(task_template=template)
        sol = self._generate_sale_order_line(sale_order=so, product=product)

        so.action_confirm()

        task = sol.task_id
        self.assertEqual(task.child_ids[0].description, template.subtasks[0].description)
        for t in task.child_ids[1:]:
            self.assertFalse(t.description)
