from odoo.tests import TransactionCase, tagged


class TestBillingContacts(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        partner = cls.env['res.partner'].create
        cls.parent_co = partner({
            'name': 'Partner',
            'company_type': 'company',
        })
        cls.billing_contact1 = partner({
            'name': 'Billing Contact 1',
            'company_type': 'person',
            'email': 'billingcontact1@partner.co',
            'parent_id': cls.parent_co.id,
            'type': 'invoice',
        })
        cls.billing_contact2 = partner({
            'name': 'Billing Contact 2',
            'company_type': 'person',
            'email': 'billingcontact2@partner.co',
            'parent_id': cls.parent_co.id,
            'type': 'invoice',
        })
        cls.non_billing_contact = partner({
            'name': 'Non-billing contact',
            'company_type': 'person',
            'email': 'not_billing@partner.co',
            'parent_id': cls.parent_co.id,
            'type': 'contact',
        })

    @tagged('-at_install', 'post_install')
    def test_sale_order_defaults(self):
        billing_contacts = self.parent_co.billing_contacts
        self.assertTrue(self.billing_contact1 in self.parent_co.billing_contacts)
        self.assertTrue(self.billing_contact2 in self.parent_co.billing_contacts)
        self.assertTrue(self.non_billing_contact not in self.parent_co.billing_contacts)
