from odoo import models, fields, api, _
from odoo.exceptions import UserError


class Partner(models.Model):
    _inherit = 'res.partner'

    is_treatment_professional = fields.Boolean(
        compute="_compute_is_treatment_professional", )
    owned_team_ids = fields.One2many(comodel_name='sports.team',
                                     inverse_name='parent_id')
    staff_ids = fields.One2many(comodel_name='sports.team.staff',
                                inverse_name='team_id')
    team_staff_rel_ids = fields.One2many(comodel_name='sports.team.staff',
                                         inverse_name='partner_id',
                                         string='Teams Served',
                                         help='The teams this person works for.')

    @api.depends('user_ids.groups_id')
    def _compute_is_treatment_professional(self):
        user_partners = self.filtered(lambda r: r.user_ids)
        non_user_partners = self - user_partners
        non_user_partners.is_treatment_professional = False
        group = self.env.ref(
            'bemade_sports_clinic.group_sports_clinic_treatment_professional')
        for rec in user_partners:
            rec.is_treatment_professional = group in rec.user_ids.groups_id
