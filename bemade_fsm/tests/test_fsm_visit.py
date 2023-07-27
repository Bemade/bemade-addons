from odoo.tests import TransactionCase, tagged, Form
from .test_bemade_fsm_common import BemadeFSMBaseTest


@tagged('-at_install', 'post_install')
class FSMVisitTest(BemadeFSMBaseTest):

    def test_create_visit_sets_name_on_section(self):
        so = self._generate_sale_order()
        self._generate_sale_order_line(sale_order=so)

        visit = self._generate_visit(so)

        self.assertTrue(visit.so_section_id)
        self.assertEqual(visit.so_section_id.name, visit.label)

    def test_change_visit_section_name(self):
        so = self._generate_sale_order()
        visit = self._generate_visit(so, label="First Label")
        line = visit.so_section_id

        line.name = "Second Label"

        self.assertEqual(visit.label, "Second Label")

    def test_change_visit_label_changes_section_name(self):
        so = self._generate_sale_order()
        visit = self._generate_visit(so, label="First Label")
        line = visit.so_section_id

        visit.label = "Second Label"

        self.assertEqual(line.name, "Second Label")

    def test_visit_completes_when_task_completes(self):
        so = self._generate_sale_order()
        visit = self._generate_visit(so)
        self._generate_sale_order_line(so)
        so.action_confirm()
        task = so.order_line.filtered(lambda l: l.task_id).task_id

        task.action_fsm_validate()

        self.assertTrue(visit.is_completed)

    def test_visit_shows_invoiced_when_invoiced(self):
        so = self._generate_sale_order()
        visit = self._generate_visit(so)
        self._generate_sale_order_line(so)
        so.action_confirm()
        task = so.order_line.filtered(lambda l: l.task_id).task_id
        task.action_fsm_validate()

        self._invoice_sale_order(so)

        self.assertTrue(visit.is_invoiced)

    def test_visit_groups_section_tasks_when_confirmed(self):
        partner = self._generate_partner()
        so = self._generate_sale_order()
        visit = self._generate_visit(sale_order=so)
        sol1 = self._generate_sale_order_line(sale_order=so)
        sol2 = self._generate_sale_order_line(sale_order=so)
        visit.so_section_id.sequence = 1
        sol1.sequence = 2
        sol2.sequence = 3

        so.action_confirm()

        visit_task = visit.task_id
        self.assertTrue(visit_task)
        visit_subtasks = visit_task.child_ids
        self.assertTrue(visit_subtasks and sol1.task_id in visit_subtasks and sol2.task_id in visit_subtasks)

    def test_adding_visit_creates_one_sale_order_line(self):
        partner = self._generate_partner()
        so = self._generate_sale_order()
        self._generate_sale_order_line(sale_order=so)
        self._generate_sale_order_line(sale_order=so)

        self._generate_visit(sale_order=so)

        self.assertEqual(len(so.order_line), 3)

    def _invoice_sale_order(self, so):
        wiz = self.env['sale.advance.payment.inv'].with_context({'active_ids': [so.id]}).create({})
        wiz.create_invoices()
        inv = so.invoice_ids[-1]
        inv.action_post()
        return inv

    def _generate_visit(self, sale_order, label="Test Label"):
        return self.env['bemade_fsm.visit'].create([{
            'sale_order_id': sale_order.id,
            'label': label,
        }])
