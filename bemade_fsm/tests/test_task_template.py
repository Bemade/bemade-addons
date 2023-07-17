from .test_bemade_fsm_common import BemadeFSMBaseTest
from odoo.tests.common import HttpCase, tagged, Form
from odoo.exceptions import MissingError
from odoo import Command
from psycopg2.errors import ForeignKeyViolation


@tagged('-at_install', 'post_install')
class TestTaskTemplate(BemadeFSMBaseTest):

    def test_delete_task_template(self):
        """User should never be able to delete a task template used on a product"""
        task_template = self._generate_task_template(names=['Template 1'])
        product = self._generate_product(name="Test Product 1", task_template=task_template)
        with self.assertRaises(ForeignKeyViolation):
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


@tagged('-at_install', 'post_install', 'slow')
class TestTaskTemplateTour(HttpCase, BemadeFSMBaseTest):

    def test_task_template_tour(self):
        user = self._generate_project_manager_user('Mister PM', 'misterpm')
        task_template = self._generate_task_template(names=['Template 1'])
        self._generate_product(name="Test Product 1", task_template=task_template)
        self.start_tour('/web', 'task_template_tour',
                        login=user.login, )
