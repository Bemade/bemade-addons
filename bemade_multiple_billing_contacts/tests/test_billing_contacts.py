from odoo.tests import TransactionCase, tagged
from odoo import Command
import datetime


@tagged('-at_install', 'post_install')
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
        cls.product = cls.env['product.product'].with_company(
            cls.parent_co.company_id).create({
            'name': 'Product',
            'categ_id': cls.env['product.category'].create(
                {'name': 'Product Category'}).id,
            'list_price': 100.0,
            'type': 'service',
            'uom_id': cls.env.ref('uom.product_uom_unit').id,
            'uom_po_id': cls.env.ref('uom.product_uom_unit').id,
            'default_code': 'PRODUCT-X',
            'invoice_policy': 'order',
            'expense_policy': 'no',
            'taxes_id': [(6, 0, [])],
            'supplier_taxes_id': [(6, 0, [])],
        })

        cls.sale_order = cls.env['sale.order'].create({
            'partner_id': cls.parent_co.id,
            'client_order_ref': 'abc123',
        })

        cls.env['sale.order.line'].create({
            'product_id': cls.product.id,
            'name': cls.product.name,
            'product_uom_qty': 2,
            'product_uom': cls.product.uom_id.id,
            'price_unit': cls.product.list_price,
            'order_id': cls.sale_order.id,
            'tax_id': False,
            'qty_delivered': 2,
            'qty_delivered_method': 'manual',
        })

    def test_billing_contacts_structure(self):
        self.assertTrue(self.billing_contact1 in self.parent_co.billing_contacts)
        self.assertTrue(self.billing_contact2 in self.parent_co.billing_contacts)
        self.assertTrue(self.non_billing_contact not in self.parent_co.billing_contacts)

    def test_sale_order_default_billing_contacts(self):
        self.assertTrue(
            self.sale_order.billing_contacts == self.parent_co.billing_contacts)

    def test_sale_order_change_contacts(self):
        # Test that changing the billing contacts on an SO doesn't change them on the partner
        self.sale_order.write(
            {'billing_contacts': [Command.link(self.non_billing_contact.id)]})
        self.assertTrue(all([c in self.sale_order.billing_contacts for c in
                             self.parent_co.billing_contacts]))
        self.assertTrue(self.non_billing_contact not in self.parent_co.billing_contacts)
        self.assertTrue(self.non_billing_contact in self.sale_order.billing_contacts)

    def test_sale_order_to_invoice_contacts(self):
        # Test that the invoices created from sales orders take the billing contacts configured on the SO

        self.sale_order.write(
            {'billing_contacts': [Command.link(self.non_billing_contact.id)]})
        self.sale_order.action_confirm()

        wiz = self.env['sale.advance.payment.inv'].create({})
        invoice = wiz._create_invoice(self.sale_order, self.sale_order.order_line[0],
                                      self.sale_order.order_line.price_total)
        self.assertTrue(invoice)
        self.assertTrue(invoice.billing_contacts == self.sale_order.billing_contacts)

    def test_direct_invoice_contacts(self):
        invoice = self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.parent_co,
        })
        self.assertTrue(self.parent_co.billing_contacts == invoice.billing_contacts)

    def test_invoice_followers_on_validate(self):
        # Make sure all billing contacts get added as followers upon validating the invoice
        self.sale_order.action_confirm()
        wiz = self.env['sale.advance.payment.inv'].create({})
        invoice = wiz._create_invoice(self.sale_order, self.sale_order.order_line[0],
                                      self.sale_order.order_line.price_total)
        invoice.write({'date': datetime.date.today()})
        invoice.action_post()
        self.assertTrue(all([r in invoice.message_partner_ids for r in
                             self.parent_co.billing_contacts]))
