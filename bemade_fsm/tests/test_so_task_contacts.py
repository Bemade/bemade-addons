from .test_task_template_sale_order import TestTaskTemplateSalesOrder
from odoo import Command


class TestSaleOrderTaskContacts(TestTaskTemplateSalesOrder):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Partner = cls.env['res.partner']
        cls.partner2 = Partner.create({
            'name': 'New Partner',
            'company_type': 'company',
        })
        cls.contact = Partner.create({
            'name': 'Contact',
            'company_type': 'person',
            'parent_id': cls.partner2.id,
        })

    def _test_contacts(self, field):
        def ga(obj):
            return getattr(obj, field)
        self.partner2.write({field: [Command.set([self.contact.id])]})
        self.sale_order1.write(
            {'partner_id': self.partner2.id, field: [Command.set(ga(self.partner2).ids)]})
        so = self.sale_order1
        self.assertTrue(ga(so))
        so.action_confirm()
        task = so.order_line[0].task_id
        self.assertTrue(ga(task))
        self.assertTrue(ga(task) == ga(so))

    def test_work_order_contacts_on_task(self):
        # Make sure work order contacts on the sales order transfer to the task on order confirmation
        self._test_contacts('work_order_contacts')

    def test_site_contacts_on_task(self):
        # Make sure site contacts from the sales order transfer to the task on order confirmation
        self._test_contacts('site_contacts')