from odoo import models, fields, api, _


class User(models.Model):
    _inherit = 'res.users'

    is_treatment_professional = fields.Boolean(
        compute="_compute_is_treatment_professional", store=True)

    @api.depends('groups_id')
    def _compute_is_treatment_professional(self):
        for rec in self:
            rec.is_treatment_professional = rec.has_group(
                'bemade_sports_clinic.group_sports_clinic_treatment_professional')
