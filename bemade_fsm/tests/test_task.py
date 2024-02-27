from .test_bemade_fsm_common import BemadeFSMBaseTest
from odoo.tests.common import tagged
from odoo import Command


@tagged('post_install', '-at_install')
class TaskTest(BemadeFSMBaseTest):

    @classmethod
    def setUpClass(cls):
        # Chose to set up all tests the same way since this code was becoming very redundant
        super().setUpClass()
        cls.so = cls._generate_sale_order()
        cls.template = cls._generate_task_template(names=['Parent', 'Child', 'Grandchild'], structure=[2, 1])
        cls.product = cls._generate_product(task_template=cls.template)
        cls.sol = cls._generate_sale_order_line(sale_order=cls.so, product=cls.product)
        cls.user = cls._generate_project_manager_user('Bob', 'Bob')
        cls.so.action_confirm()
        cls.task = cls.sol.task_id

    def test_reassigning_assignment_propagating_task_changes_subtasks(self):
        task = self.task
        task.propagate_assignment = True

        task.write({
            'user_ids': [Command.set([self.user.id])],
            'propagate_assignment': True,
        })

        self.assertTrue(all([t.user_ids == self.user for t in task | task._get_all_subtasks()]))

    def test_reassigning_task_doesnt_propagate_by_default(self):
        task = self.task
        task.write({
            'user_ids': [Command.set([self.user.id])],
            'propagate_assignment': True,
        })

        self.assertFalse(any([t.user_ids for t in task.child_ids.child_ids]))

    def test_unset_propagate_assignment_unsets_for_all_children(self):
        task = self.task
        # First, set propagation and assign
        task.propagate_assignment = True
        task.write({
            'user_ids': [Command.set([self.user.id])]
        })
        # Then, unset propagation for the children and re-set assignment
        task.child_ids.write({'propagate_assignment': False})
        self.assertFalse(any([t.propagate_assignment for t in task._get_all_subtasks()]))
        # Then, test that assigning the parent only assigns its children, not its grandchildren
        task.write({
            'user_ids': [Command.set([])]
        })
        self.assertTrue(all([not t.user_ids for t in task | task.child_ids]))
        self.assertTrue(all([t.user_ids == self.user for t in task.child_ids.child_ids]))
