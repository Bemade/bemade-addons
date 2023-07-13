from odoo import models, fields, api, _


class FSMVisit(models.Model):
    _name = "bemade_fsm.visit"
    _description = 'Represents a single visit by assigned service personnel.'

    label = fields.Text(string="Label",
                        required=True,
                        related='so_section_id.name',
                        readonly=False)
    approx_date = fields.Date(string='Approximate Date')
    so_section_id = fields.Many2one(comodel_name="sale.order.line",
                                    string="Sale Order Section",
                                    help="The section on the sale order that represents the labour and parts for "
                                         "this visit")
    sale_order_id = fields.Many2one(comodel_name="sale.order",
                                    string="Sales Order",
                                    required=True)
    is_completed = fields.Boolean(string="Completed",
                                  related="so_section_id.is_fully_delivered")
    is_invoiced = fields.Boolean(string="Invoiced",
                                 related="so_section_id.is_fully_delivered_and_invoiced")

    def _compute_is_invoiced(self):
        self.is_invoiced = False

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        for i, rec in enumerate(recs):
            rec.so_section_id = rec.env['sale.order.line'].create({
                'order_id': rec.sale_order_id.id,
                'display_type': 'line_section',
                'name': vals_list[i]['label'],
            })
        return recs
