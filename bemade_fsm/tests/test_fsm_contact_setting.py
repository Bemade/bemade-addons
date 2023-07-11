from odoo.tests import TransactionCase, HttpCase, tagged, Form
from odoo import Command
from .test_bemade_fsm_common import FSMManagerUserTransactionCase


def create_base_contacts(cls):
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


@tagged("-at_install", "post_install")
class SaleOrderFSMContactsCase(FSMManagerUserTransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        create_base_contacts(cls)

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


class SaleOrderMultiLocationContactsTest(FSMManagerUserTransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        create_base_contacts(cls)
        cls.shipping_location = cls.env['res.partner'].create({
            'name': 'Shipping location',
            'company_type': 'company',
            'type': 'delivery',
            'parent_id': cls.parent_co.id,
        })
        cls.site_contact1 = cls.env['res.partner'].create({
            'name': 'Site Contact One',
            'company_type': 'person',
            'type': 'contact',
            'parent_id': cls.shipping_location.id,
        })
        cls.site_contact2 = cls.env['res.partner'].create({
            'name': 'Site Contact Two',
            'company_type': 'person',
            'type': 'contact',
            'parent_id': cls.shipping_location.id,
        })
        cls.shipping_location.write({
            'work_order_contacts': [Command.set([cls.contact_1.id, cls.contact_2.id])],
            'site_contacts': [Command.set([cls.site_contact1.id, cls.site_contact2.id])],
        })

    def test_multilayer_site_contacts(self):
        so = self.env['sale.order'].create({
            'partner_id': self.parent_co.id,
            'partner_shipping_id': self.shipping_location.id})
        self.assertEqual(so.partner_shipping_id, self.shipping_location)
        self.assertEqual(so.site_contacts, self.shipping_location.site_contacts)
        self.assertEqual(so.work_order_contacts, self.shipping_location.work_order_contacts)

    def test_onchange_shipping_address(self):
        so = self.env['sale.order'].create({
            'partner_id': self.parent_co.id,
            'partner_shipping_id': self.parent_co.id,
        })
        self.assertFalse(so.work_order_contacts)
        self.assertFalse(so.site_contacts)

        form = Form(so)
        form.partner_shipping_id = self.shipping_location
        form.save()

        self.assertEqual(so.work_order_contacts, self.shipping_location.work_order_contacts)
        self.assertEqual(so.site_contacts, self.shipping_location.site_contacts)
