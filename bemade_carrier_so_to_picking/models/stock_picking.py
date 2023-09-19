from odoo import fields, models, api, _, Command


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    carrier_id = fields.Many2one("delivery.carrier",
                                 string="Carrier",
                                 check_company=True,
                                 compute='_compute_carrier_id',
                                 inverse='_inverse_carrier_id',
                                 store=True)
    # carrier_set_manually = fields.Boolean(default=False)

    @api.depends('sale_id')
    def _compute_carrier_id(self):
        for rec in self:
            # rec.carrier_id = rec.carrier_set_manually and rec.carrier_id \
            #                  or rec.sale_id and rec.sale_id.carrier_id
            rec.carrier_id = rec.sale_id and rec.sale_id.carrier_id

    def _inverse_carrier_id(self):
        # self.carrier_set_manually = True
        pass
