from odoo import models, fields, api

class CreatePropertyWizard(models.TransientModel):
    _name = 'create.property.wizard'
    _description = 'Property Wizard'

    property_id = fields.Many2one(
        comodel_name='res.partner',
        string='Property',
        domain=[('is_property', '=', True)],
        required=True
    )

    def action_done(self):
        # Here process your data, for example:
        self.env['res.partner'].browse(self._context.get('active_ids')).write({'property_id': self.property_id.id})

    def action_create_property(self):
        # Redirect to the form view of 'res.partner' for user to create new property
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'res.partner',
            'view_mode': 'form',
            'view_type': 'form',
            'context': {"default_is_property": True},
            'target': 'new',
        }

    def action_select_property(self):
        # wizard action goes here. Use self.partner_id for selected property
        pass