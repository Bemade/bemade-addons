from .test_bemade_fsm_common import BemadeFSMBaseTest
from odoo.tests.common import HttpCase, tagged, Form
from odoo.exceptions import MissingError
from odoo import Command
from odoo.tools import mute_logger
from psycopg2.errors import ForeignKeyViolation


@tagged('-at_install', 'post_install')
class TestTaskTemplate(BemadeFSMBaseTest):

    def test_delete_task_template(self):
        """User should never be able to delete a task template used on a product"""
        task_template = self._generate_task_template(names=['Template 1'])
        product = self._generate_product(name="Test Product 1", task_template=task_template)
        with self.assertRaises(ForeignKeyViolation):
            with mute_logger('odoo.sql_db'):
                task_template.unlink()

    def test_delete_subtask_template(self):
        """ Deletion of a child task should be OK even if the parent is on a product. Children of the deleted
        subtask should be deleted."""
        parent_task = self._generate_task_template(structure=[2, 1],
                                                   names=['Parent Template', 'Child Template',
                                                          'Grandchild Template'])
        grandchild_task = parent_task.subtasks[0].subtasks[0]

        parent_task.subtasks[0].unlink()

        # Reading deleted child's name field should be impossible
        with self.assertRaises(MissingError):
            test = grandchild_task.name

    def test_dissociating_customer_resets_equipment_appropriately(self):
        partner1 = self._generate_partner()
        partner2 = self._generate_partner()
        equipment1 = self._generate_equipment(partner=partner1)
        task = self._generate_task_template(customer=partner1, equipment=equipment1)
        form = Form(task)

        # Switching the partner should trigger on_change that makes sure equipments are linked to the new partner
        form.customer = partner2
        form.save()

        self.assertFalse(equipment1 in task.equipment_ids)

    def test_hours_estimate_used_for_planning(self):
        partner = self._generate_partner()
        so = self._generate_sale_order(partner=partner)
        task_template = self._generate_task_template(planned_hours=8)
        product = self._generate_product(uom=self.env.ref('uom.product_uom_unit'), task_template=task_template)

        sol = self._generate_sale_order_line(sale_order=so, product=product)

        self.assertEqual(sol.task_duration, 8)

    def test_hours_estimate_multiplied_for_multiple_units_sold(self):
        partner = self._generate_partner()
        so = self._generate_sale_order(partner=partner)
        task_template = self._generate_task_template(planned_hours=8)
        product = self._generate_product(uom=self.env.ref('uom.product_uom_unit'),
                                         task_template=task_template)

        sol = self._generate_sale_order_line(sale_order=so, product=product, qty=3.0)

        self.assertEqual(sol.task_duration, 24)

    def test_child_task_names_are_short_version(self):
        so, visit, sol1, sol2 = self._generate_so_with_one_visit_two_lines()
        template = self._generate_task_template(names=['Task'])
        product = self._generate_product(task_template=template)
        sol1.name = "Short Name 1"
        sol2.name = "Short Name 2"
        sol3 = self._generate_sale_order_line(sale_order=so, product=product)

        so.action_confirm()

        self.assertEqual(sol1.task_id.name, "Short Name 1")
        self.assertEqual(sol2.task_id.name, "Short Name 2")
        self.assertEqual(sol3.task_id.name, "Task")

    def test_task_creation_directly_from_template(self):
        project = self.env.ref("industry_fsm.fsm_project")
        template = self._generate_task_template(names=['Task', 'Child', 'Grandchild'], structure=[2, 1])

        task = template.create_task_from_self(project, "My new task")

        self.assertEqual(len(task.child_ids), len(template.subtasks))
        self.assertEqual(len(task.child_ids[0].child_ids), len(template.subtasks[0].subtasks))
        self.assertEqual(len(task.child_ids[1].child_ids), len(template.subtasks[1].subtasks))
        self.assertEqual(task.name, "My new task")
        self.assertEqual(task.child_ids[0].name, template.subtasks[0].name)
        self.assertTrue(all([t.project_id == project for t in task | task._get_all_subtasks()]))

