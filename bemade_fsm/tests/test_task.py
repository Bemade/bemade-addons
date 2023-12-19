from .test_bemade_fsm_common import BemadeFSMBaseTest
from odoo.tests.common import tagged
from odoo import Command


@tagged('post_install', '-at_install')
class TaskTest(BemadeFSMBaseTest):

    def test_reassigning_assignment_propagating_task_changes_subtasks(self):
        # This creation step is a bit lazy - we use defaults to make tasks with a hierachy and settings we want
        so = self._generate_sale_order()
        template = self._generate_task_template(names=['Parent', 'Child'], structure=[2])
        product = self._generate_product(task_template=template)
        sol = self._generate_sale_order_line(sale_order=so, product=product)
        user = self._generate_project_manager_user('Bob', 'Bob')
        so.action_confirm()
        task = sol.task_id

        task.write({
            'user_ids': [Command.set([user.id])]
        })

        self.assertTrue(all([t.user_ids == user for t in task | task._get_all_subtasks()]))

    def test_reassigning_assignment_non_propagating_task_doesnt_change_subtasks(self):
        so = self._generate_sale_order()
        template = self._generate_task_template(names=['Parent', 'Child', 'Grandchild'], structure=[2, 1])
        product = self._generate_product(task_template=template)
        sol = self._generate_sale_order_line(sale_order=so, product=product)
        user = self._generate_project_manager_user('Bob', 'Bob')
        so.action_confirm()
        task = sol.task_id
        task.child_ids.write({'propagate_assignment': False})  # Stop propagation after the first level

        task.write({
            'user_ids': [Command.set([user.id])]
        })

        self.assertTrue(all([t.user_ids == user for t in task | task.child_ids]))
        self.assertFalse(any([t.user_ids for t in task.child_ids.child_ids]))
