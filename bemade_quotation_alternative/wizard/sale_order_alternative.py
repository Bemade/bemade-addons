from odoo import fields, models, api
import string


class AlternativeQuotation(models.TransientModel):
    _name = 'sale.order.alternative'
    _description = 'Quotation Alternative'

    name = fields.Char()
    original_sale_order_id = fields.Many2one('sale.order')

    clone_all_lines = fields.Boolean('Clone all lines', default=True)
    origin = fields.Text('Why this alternative ?')
    internal_note = fields.Text('Internal Note')

    def action_create_alternative(self):
        name = self.original_sale_order_id.name

        if name and name[-1] not in string.ascii_letters:
            self.original_sale_order_id.name = name + "A"
            name = self.name + "B"
        else:
            # Assuming 'all_names' is a list of all names
            # Add a domain to filter names starting with 'name' (less the last letter)
            all_names = [record.name for record in self.env['sale.order'].search([('name', 'like', name[:-1] + '%')])]
            if name in all_names:
                # Get the index of the current name in the list
                index = all_names.index(name)
                # If this is not the last name in the list, get the next one
                if index < len(all_names) - 1:
                    name = all_names[index + 1]
                else:
                    # If this is the last name, just add 'B' to it
                    name = name + "B"

            new_quot = quot.original_sale_order_id.copy({
                'name': quot.name,
                'origin': quot.original_sale_order_id.name,
                'alternative_sale_order_id': quot.original_sale_order_id.id,
                'alternative': True,
                'alternative_origine': quot.origine,
                'alternative_internal_note': quot.internal_note,

#     # Lines and line based computes
#     order_line = fields.One2many(
#         comodel_name='sale.order.alternative.line',
#         inverse_name='order_id',
#         string="Order Lines",
#         copy=True, auto_join=True)
#
# class AlternativeQuotation(models.TransientModel):
#     _name = 'sale.order.alternative.line'
#     # _inherit = 'sale.order.line'
#     _description = 'Quotation Alternative Line'
#
#     order_id = fields.Many2one(
#         comodel_name='sale.order.alternative',
#         string="Alternative Quotation Reference",
#         required=True, ondelete='cascade', index=True, copy=False)
