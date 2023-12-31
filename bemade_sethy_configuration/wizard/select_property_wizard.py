from odoo import models, fields, api

class AddPropertyWizard(models.TransientModel):
    _name = 'add.property.wizard'

    property_id = fields.Many2one('res.partner', string='Property', domain=[('is_property', '=', True)])

    def action_done(self):
        # Here process your data, for example:
        self.env['res.partner'].browse(self._context.get('active_ids')).write({'property_id': self.property_id.id})
