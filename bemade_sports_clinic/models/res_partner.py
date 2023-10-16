from odoo import models, fields, api, _
from odoo.exceptions import UserError


class Partner(models.Model):
    _inherit = 'res.partner'

    patient_ids = fields.Many2many(comodel_name='sports.patient',
                                   relation='sports_team_patient_rel',
                                   column1='team_id',
                                   column2='patient_id',
                                   string='Players')
    type = fields.Selection(selection_add=[('team', 'Sports Team'),])
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
