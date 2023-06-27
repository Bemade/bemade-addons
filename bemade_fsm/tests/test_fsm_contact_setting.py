from odoo.tests import TransactionCase, HttpCase, tagged
from odoo import Command
from .test_bemade_fsm_common import FSMManagerUserTransactionCase


@tagged("-at_install", "post_install")
class SaleOrderFSMContactsCase(FSMManagerUserTransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Partner = cls.env['res.partner']
        cls.parent_co = Partner.create({
            'name': 'Parent Co',
            'company_type': 'company',
        })
        cls.contact_1 = Partner.create({
            'name': 'Contact 1',
            'company_type': 'person',
            'parent_id': cls.parent_co.id,
        })
        cls.contact_2 = Partner.create({
            'name': 'Contact 2',
            'company_type': 'person',
            'parent_id': cls.parent_co.id,
        })

    def test_site_contacts(self):
        # Make sure the SO pulls the defaults from the partner correctly
        self.parent_co.write({'site_contacts': [Command.set([self.contact_1.id, self.contact_2.id])]})
        so = self.env['sale.order'].create({
            'partner_id': self.parent_co.id,
        })
        self.assertTrue(so.site_contacts == self.parent_co.site_contacts)
        # Make sure updating the site contacts on the SO doesn't feed back to the partner
        so.write({'site_contacts': [Command.set([self.contact_1.id])]})
        self.assertTrue(self.contact_1 in so.site_contacts)
        self.assertTrue(self.contact_2 not in so.site_contacts)
        self.assertTrue(so.site_contacts != so.partner_id.site_contacts and len(so.partner_id.site_contacts) == 2)

    def test_default_workorder_contacts(self):
        # Make sure the SO pulls the defaults from the partner correctly
        self.parent_co.write({'work_order_contacts': [Command.set([self.contact_1.id, self.contact_2.id])]})
        so = self.env['sale.order'].create({
            'partner_id': self.parent_co.id,
        })
        self.assertTrue(self.contact_1 in self.parent_co.work_order_contacts)
        self.assertTrue(self.contact_2 in self.parent_co.work_order_contacts)
        self.assertTrue(self.contact_1 in so.work_order_contacts)
        self.assertTrue(self.contact_2 in so.work_order_contacts)
        # Make sure setting the work order contacts on the SO doesn't feed back to the partner
        so.write({'work_order_contacts': [Command.set([self.contact_1.id])]})
        self.assertTrue(self.contact_1 in so.work_order_contacts)
        self.assertTrue(self.contact_2 not in so.work_order_contacts)
        self.assertTrue(
            so.work_order_contacts != so.partner_id.work_order_contacts and len(so.partner_id.work_order_contacts) == 2)
