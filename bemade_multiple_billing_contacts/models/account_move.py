from odoo import models, fields, api


class AccountMove(models.Model):
    _inherit = 'account.move'

    billing_contacts = fields.Many2many(
        comodel_name='res.partner',
        string="Billing Contacts",
        compute='_compute_billing_contacts',
        inverse='_inverse_billing_contacts',
        store=True
    )

    @api.depends('line_ids.sale_line_ids.order_id', 'partner_id')
    def _compute_billing_contacts(self):
        for rec in self:
            order_id = rec.line_ids and rec.line_ids.mapped('sale_line_ids').mapped('order_id')
            if order_id and len(order_id) == 1 and order_id.billing_contacts:
                rec.billing_contacts = order_id.billing_contacts
            else:
                rec.billing_contacts = rec.partner_id.billing_contacts

    def _inverse_billing_contacts(self):
        pass

    def _post(self, soft=True):
        # Override the original method to subscribe the partner's billing contacts instead of self.partner_id
        initial_subscribers = self.message_partner_ids.ids
        final_subscribers = initial_subscribers + self.billing_contacts.ids
        posted = super()._post()
        self.message_unsubscribe([s.id for s in self.message_partner_ids if s.id not in initial_subscribers])
        self.message_subscribe(final_subscribers)
        return posted
