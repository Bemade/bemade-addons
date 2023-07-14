from odoo.tests import TransactionCase, HttpCase, tagged, Form
from odoo import Command
from .test_bemade_fsm_common import BemadeFSMBaseTest


@tagged("-at_install", "post_install")
class SaleOrderFSMContactsCase(BemadeFSMBaseTest):

    def test_site_contacts(self):
        parent_co = self._generate_partner('Parent Co')
        contact_1 = self._generate_partner('Contact 1', 'person', parent_co)
        contact_2 = self._generate_partner('Contact 2', 'person', parent_co)

        # Make sure the SO pulls the defaults from the partner correctly
        parent_co.write({'site_contacts': [Command.set([contact_1.id, contact_2.id])]})
        so = self._generate_sale_order(parent_co)
        self.assertTrue(so.site_contacts == parent_co.site_contacts)

        # Make sure updating the site contacts on the SO doesn't feed back to the partner
        so.write({'site_contacts': [Command.set([contact_1.id])]})
        self.assertTrue(contact_1 in so.site_contacts)
        self.assertTrue(contact_2 not in so.site_contacts)
        self.assertTrue(so.site_contacts != so.partner_id.site_contacts and len(so.partner_id.site_contacts) == 2)

    def test_default_workorder_contacts(self):
        parent_co = self._generate_partner('Parent Co')
        contact_1 = self._generate_partner('Contact 1', 'person', parent_co)
        contact_2 = self._generate_partner('Contact 2', 'person', parent_co)

        # Make sure the SO pulls the defaults from the partner correctly
        parent_co.write({'work_order_contacts': [Command.set([contact_1.id, contact_2.id])]})
        so = self._generate_sale_order(parent_co)
        self.assertTrue(contact_1 in parent_co.work_order_contacts)
        self.assertTrue(contact_2 in parent_co.work_order_contacts)
        self.assertTrue(contact_1 in so.work_order_contacts)
        self.assertTrue(contact_2 in so.work_order_contacts)

        # Make sure setting the work order contacts on the SO doesn't feed back to the partner
        so.write({'work_order_contacts': [Command.set([contact_1.id])]})
        self.assertTrue(contact_1 in so.work_order_contacts)
        self.assertTrue(contact_2 not in so.work_order_contacts)
        self.assertTrue(
            so.work_order_contacts != so.partner_id.work_order_contacts and len(so.partner_id.work_order_contacts) == 2)

    def test_multilayer_site_contacts(self):
        parent_co = self._generate_partner('Parent Co')
        shipping_location = self._generate_partner('Shipping Location', 'company', parent_co, 'delivery')
        wo_contact_1 = self._generate_partner('WO Contact 1', 'person', shipping_location)
        wo_contact_2 = self._generate_partner('WO Contact 2', 'person', shipping_location)
        site_contact_1 = self._generate_partner('Site Contact 1', 'person', shipping_location)
        site_contact_2 = self._generate_partner('Site Contact 2', 'person', shipping_location)
        shipping_location.write({
            'work_order_contacts': [Command.set([wo_contact_1.id, wo_contact_2.id])],
            'site_contacts': [Command.set([site_contact_1.id, site_contact_2.id])]
        })

        so = self._generate_sale_order(parent_co)
        so.write({'partner_shipping_id': shipping_location.id})

        self.assertEqual(so.site_contacts, shipping_location.site_contacts)
        self.assertEqual(so.work_order_contacts, shipping_location.work_order_contacts)

    def test_onchange_shipping_address(self):
        parent_co = self._generate_partner('Parent Co')
        shipping_location = self._generate_partner('Shipping Location', 'company', parent_co, 'delivery')
        wo_contact_1 = self._generate_partner('WO Contact 1', 'person', shipping_location)
        wo_contact_2 = self._generate_partner('WO Contact 2', 'person', shipping_location)
        site_contact_1 = self._generate_partner('Site Contact 1', 'person', shipping_location)
        site_contact_2 = self._generate_partner('Site Contact 2', 'person', shipping_location)
        shipping_location.write({
            'work_order_contacts': [Command.set([wo_contact_1.id, wo_contact_2.id])],
            'site_contacts': [Command.set([site_contact_1.id, site_contact_2.id])]
        })

        so = self._generate_sale_order(parent_co)

        # Set back to a location without site or work order contacts
        form = Form(so)
        form.partner_shipping_id = parent_co
        form.save()
        # Make sure the contacts were reset on the SO
        self.assertFalse(so.work_order_contacts)
        self.assertFalse(so.site_contacts)

        # Now set back to the location with the FSM contacts and make sure they get set on the SO
        form.partner_shipping_id = shipping_location
        form.save()
        self.assertEqual(so.work_order_contacts, shipping_location.work_order_contacts)
        self.assertEqual(so.site_contacts, shipping_location.site_contacts)
