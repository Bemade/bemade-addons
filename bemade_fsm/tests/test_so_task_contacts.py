from .test_sale_order import TestSalesOrder
from odoo import Command
from odoo.tests.common import Form, tagged


@tagged("-at_install", "post_install")
class TestSaleOrderTaskContacts(TestSalesOrder):
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
        cls.contact2 = cls.env['res.partner'].create({
            'name': 'Contact 2',
            'company_type': 'person',
            'parent_id': cls.partner2.id,
        })

    def _test_task_contacts_from_so(self, field):
        """ Shorthand function for testing both work_order_contacts and site_contacts fields on SOs and tasks."""
        def ga(obj):
            return getattr(obj, field)
        # Add the default site/work order contact to the partner, create an SO with the partner
        self.partner2.write({field: [Command.set([self.contact.id])]})
        self.sale_order1.write(
            {'partner_id': self.partner2.id, field: [Command.set(ga(self.partner2).ids)]})
        so = self.sale_order1
        self.assertTrue(ga(so))
        # Confirm the SO and check that the task got the default carried over
        so.action_confirm()
        task = so.order_line[0].task_id
        self.assertTrue(ga(task))
        self.assertTrue(ga(task) == ga(so))
        # Now change the site/work order contact on the task and make sure it feeds back to the sales order
        f = Form(task)
        ga(f).add(self.contact2)
        f.save()
        self.assertTrue(ga(so) == ga(task))
        # Test changing it on the SO feeds back to the task as well
        f = Form(so)
        ga(f).remove(self.contact.id)
        f.save()
        self.assertTrue(ga(so) == ga(task))

    def test_work_order_contacts_on_task(self):
        # Make sure work order contacts on the sales order transfer to the task on order confirmation
        self._test_task_contacts_from_so('work_order_contacts')

    def test_site_contacts_on_task(self):
        # Make sure site contacts from the sales order transfer to the task on order confirmation
        self._test_task_contacts_from_so('site_contacts')
