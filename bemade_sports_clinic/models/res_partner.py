from odoo import models, fields, api, _
from odoo.exceptions import UserError


class Partner(models.Model):
    _inherit = 'res.partner'

    patient_ids = fields.Many2many(comodel_name='sports.patient',
                                   relation='sports_team_patient_rel',
                                   column1='team_id',
                                   column2='patient_id',
                                   string='Players')
    player_count = fields.Integer(compute="_compute_player_counts")
    injured_count = fields.Integer(compute="_compute_player_counts")
    type = fields.Selection(selection_add=[('team', 'Sports Team'), ])
    staff_partner_ids = fields.Many2many(comodel_name='res.partner',
                                         relation='sports_team_staff_partner_rel',
                                         column1='team_id',
                                         column2='staff_partner_id',
                                         string='Staff')
    staff_team_ids = fields.Many2many(comodel_name='res.partner',
                                      relation='sports_team_staff_partner_rel',
                                      column1='staff_partner_id',
                                      column2='team_id',
                                      string='Teams')

    is_treatment_professional = fields.Boolean(
        compute="_compute_is_treatment_professional",
        store=True)

    def write(self, vals):
        teams = self.filtered(lambda r: r.type == 'team')
        if teams and 'type' in vals and vals['type'] != 'team':
            if teams.mapped('staff_partner_ids') or teams.mapped('patient_ids'):
                raise UserError(_('Sports team is related to patients and/or staff. '
                                  'Its type cannot be changed until these relations are '
                                  'removed.'))
        return super().write(vals)

    def unlink(self):
        teams = self.filtered(lambda r: r.type == 'team')
        if teams:
            if teams.mapped('staff_partner_ids') or teams.mapped('patient_ids'):
                raise UserError(_('Sports team is related to patients and/or staff. '
                                  'Its type cannot be deleted until these relations are '
                                  'removed. You may try archiving it instead.'))
        return super().unlink()

    @api.depends('user_ids.groups_id')
    def _compute_is_treatment_professional(self):
        user_partners = self.filtered(lambda r: r.user_ids)
        non_user_partners = self - user_partners
        non_user_partners.is_treatment_professional = False
        group = self.env.ref(
            'bemade_sports_clinic.group_sports_clinic_treatment_professional')
        for rec in user_partners:
            rec.is_treatment_professional = group in rec.user_ids.groups_id

    def _compute_player_counts(self):
        for rec in self:
            rec.player_count = len(rec.patient_ids)
            rec.injured_count = len(rec.patient_ids.filtered(lambda p: p.is_injured))