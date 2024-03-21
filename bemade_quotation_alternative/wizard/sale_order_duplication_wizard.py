from odoo import models, fields, api

class SaleOrderDuplicationWizard(models.TransientModel):
    _name = 'sale.order.duplication.wizard'
    _description = 'Wizard for duplicating a sale order'

    original_order_id = fields.Many2one('sale.order', string='Original Order', required=True)
    new_quot = fields.Char(string='New Quotation Name', compute='_compute_new_quot', store=True)

    duplicate_all_lines = fields.Boolean(string='Duplicate All Lines?', default=True)
    lines_to_duplicate = fields.One2many(
        'sale.order.line.duplication.wizard', 'wizard_id',
        string="Lines to Duplicate",
        context={'default_original_order_id': original_order_id},
    )

    purpose = fields.Text(string='Purpose')
    note = fields.Html(string='Note')

    @api.model
    def default_get(self, fields_list):
        res = super(SaleOrderDuplicationWizard, self).default_get(fields_list)
        if 'default_original_order_id' in self.env.context:
            original_order_id = self.env.context['default_original_order_id']
            original_order = self.env['sale.order'].browse(original_order_id)
            lines_vals = []
            for line in original_order.order_line:
                lines_vals.append((0, 0, {'sale_order_line_id': line.id}))
            res.update({
                'lines_to_duplicate': lines_vals,
                'purpose': original_order.purpose if 'purpose' in fields_list else '',
                'note': original_order.note if 'note' in fields_list else '',
            })
        return res

    def action_duplicate_order(self):
        self.ensure_one()
        # Duplication de la commande de vente
        new_order = self.original_order_id.copy({
            'purpose': self.purpose,
            'note': self.note,
            # Assurez-vous que 'new_quot' est défini correctement dans votre modèle
            'name': self.new_quot,
        })
        if not self.duplicate_all_lines:
            new_order.order_line.unlink()
            for line_wiz in self.lines_to_duplicate.filtered('to_duplicate'):
                line_wiz.sale_order_line_id.copy({'order_id': new_order.id})

        # Préparation et envoi des messages de notification dans le chatter
        user_name = self.env.user.name
        now = fields.Datetime.now()

        # Message pour la commande originale
        original_msg_body = f"A new quotation <a href='#' data-oe-model='sale.order' data-oe-id='{new_order.id}'>#{new_order.name}</a> created by {user_name} duplicating this Quotation."
        self.original_order_id.message_post(body=original_msg_body)

        # Message pour la nouvelle commande dupliquée
        new_msg_body = f"This quotation has been created by {user_name} duplicating the original Quotation <a href='#' data-oe-model='sale.order' data-oe-id='{self.original_order_id.id}'>#{self.original_order_id.name}</a>."
        new_order.message_post(body=new_msg_body)

        return {
            'type': 'ir.actions.act_window',
            'name': 'Duplicated Order',
            'res_model': 'sale.order',
            'res_id': new_order.id,
            'view_mode': 'form',
            'target': 'current',
        }

    @api.depends('original_order_id')
    def _compute_new_quot(self):

        for rec in self:
            original_order_name = rec.original_order_id.name.split('-')[
                0] if '-' in rec.original_order_id.name else rec.original_order_id.name
            other_quotes = self.env['sale.order'].search([('name', 'like', original_order_name + '%')])
            rec.new_quot = original_order_name + '-REV' + str(len(other_quotes))
