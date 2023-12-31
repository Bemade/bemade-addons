from odoo import models, api

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    def set_values(self):
        res = super().set_values()
        category_id = self.env.ref('bemade_sethy_configuration.partner_tag_property', raise_if_not_found=False)
        # If the category_id record exists, we set its ID in ir.config_parameter
        if category_id:
            self.env['ir.config_parameter'].sudo().set_param('bemade_sethy_configuration.partner_tag_property', category_id.id)
        return res