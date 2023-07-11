from odoo.tests import TransactionCase, tagged, Form


@tagged('-at_install', 'post_install')
class FSMVisitTest(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

    def test_create_visit_sets_name_on_section(self):
        so = self.generate_sale_order()
        self.add_service_so_line(so)

        visit = self.generate_visit(so)

        self.assertTrue(visit.so_section_id)
        self.assertEqual(visit.so_section_id.name, visit.label)

    def test_change_visit_section_name(self):
        so = self.generate_sale_order()
        visit = self.generate_visit(so, label="First Label")
        line = visit.so_section_id

        line.name = "Second Label"

        self.assertEqual(visit.label, "Second Label")

    def test_change_visit_label_changes_section_name(self):
        so = self.generate_sale_order()
        visit = self.generate_visit(so, label="First Label")
        line = visit.so_section_id

        visit.label = "Second Label"

        self.assertEqual(line.name, "Second Label")

    def test_visit_completes_when_task_completes(self):
        so = self.generate_sale_order()
        visit = self.generate_visit(so)
        sol = self.add_service_so_line(so, task=True)
        so.action_confirm()
        task = so.order_line.filtered(lambda l: l.task_id).task_id

        task.action_fsm_validate()

        self.assertTrue(visit.is_completed)

    def generate_visit(self, sale_order, label="Test Label"):
        return self.env['bemade_fsm.visit'].create([{
            'sale_order_id': sale_order.id,
            'label': label,
        }])

    def generate_sale_order(self, partner_id=None):
        so = self.env['sale.order'].create({
            'partner_id': partner_id or self.generate_partner().id,
            'client_order_ref': 'Test',
        })
        return so

    def add_service_so_line(self, sale_order, task: bool = False):
        """ Generates a sales order line for a service product.

        :param sale_order: The sales order to which the new line is to be added
        :param task: If true, the created line will be for a product with service_tracking=task_global_project
        """
        if not task:
            service_tracking = 'no'
            project = False
        else:
            project = self.env.ref("industry_fsm.fsm_project")
            service_tracking = 'task_global_project'
        product = self.env['product.product'].create({
            'name': 'Test Product',
            'type': 'service',
            'service_tracking': service_tracking,
            'project_id': project and project.id,
            'price': 100.0,
            'sale_ok': True,
        })
        return self.env['sale.order.line'].create({
            'product_id': product.id,
            'order_id': sale_order.id,
        })

    def generate_partner(self):
        partner = self.env['res.partner'].create({
            'name': 'Test Partner',
            'company_type': 'company',
        })
        return partner
