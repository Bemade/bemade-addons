from odoo.tests import TransactionCase, tagged, Form
from .test_bemade_fsm_common import BemadeFSMBaseTest


@tagged('-at_install', 'post_install')
class FSMVisitTest(BemadeFSMBaseTest):

    def test_create_visit_sets_name_on_section(self):
        so = self._generate_sale_order()
        self._add_service_so_line(so)

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
        self._add_service_so_line(so, task=True)
        so.action_confirm()
        task = so.order_line.filtered(lambda l: l.task_id).task_id

        task.action_fsm_validate()

        self.assertTrue(visit.is_completed)

    def test_visit_shows_invoiced_when_invoiced(self):
        so = self._generate_sale_order()
        visit = self._generate_visit(so)
        self._add_service_so_line(so, task=True)
        so.action_confirm()
        task = so.order_line.filtered(lambda l: l.task_id).task_id
        task.action_fsm_validate()

        self._invoice_sale_order(so)

        self.assertTrue(visit.is_invoiced)

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

    def _add_service_so_line(self, sale_order, task: bool = False):
        """ Generates a sales order line for a service product.

        :param sale_order: The sales order to which the new line is to be added
        :param task: If true, the created line will be for a product with service_tracking=task_global_project
        """
        service_tracking = 'task_global_project' if task else 'no'
        product = self._generate_product(service_tracking=service_tracking)
        return self._generate_sale_order_line(sale_order, product)
