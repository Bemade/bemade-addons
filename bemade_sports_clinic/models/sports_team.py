from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class SportsTeam(models.Model):
    _name = "sports.team"
    _description = "Sports Team"

    name = fields.Char()
    patient_ids = fields.Many2many(comodel_name='sports.patient',
                                   relation='sports_team_patient_rel',
                                   column1='team_id',
                                   column2='patient_id',
                                   string='Players')
    player_count = fields.Integer(compute="_compute_player_counts")
    injured_count = fields.Integer(compute="_compute_player_counts")
    healthy_count = fields.Integer(compute="_compute_player_counts")
    parent_id = fields.Many2one(comodel_name='res.partner', string='Parent Organization',
                                ondelete='restrict')
    staff_ids = fields.One2many(comodel_name='sports.team.staff',
                                inverse_name='team_id')
    head_coach_id = fields.Many2one(comodel_name='res.partner',
                                    compute='_compute_head_coach',
                                    store=True)
    head_coach_name = fields.Char(related='head_coach_id.name')
    head_trainer_id = fields.Many2one(comodel_name='res.partner',
                                      compute='_compute_head_trainer',
                                      store=True)
    head_trainer_name = fields.Char(related='head_trainer_id.name')
    website = fields.Char()

    @api.depends('patient_ids.is_injured')
    def _compute_player_counts(self):
        for rec in self:
            rec.player_count = len(rec.patient_ids)
            rec.injured_count = len(rec.patient_ids.filtered(lambda p: p.is_injured))
            rec.healthy_count = rec.player_count - rec.injured_count

    @api.depends('staff_ids.role')
    def _compute_head_coach(self):
        for rec in self:
            staff = rec.staff_ids.filtered(lambda r: r.role == 'head_coach')
            rec.head_coach_id = staff.partner_id if staff else False

    @api.depends('staff_ids.role')
    def _compute_head_trainer(self):
        for rec in self:
            staff = rec.staff_ids.filtered(lambda r: r.role == 'head_trainer')
            rec.head_trainer_id = staff.partner_id if staff else False


class TeamStaff(models.Model):
    _name = "sports.team.staff"
    _description = "Relationship between staff members and their teams."

    sequence = fields.Integer()
    team_id = fields.Many2one(comodel_name='sports.team', string='Team', required=True)
    partner_id = fields.Many2one(comodel_name='res.partner', string='Staff Member',
                                 required=True)
    role = fields.Selection(selection=[
        ('head_coach', 'Head Coach'),
        ('head_trainer', 'Head Trainer'),
        ('coach', 'Coach'),
        ('trainer', 'Trainer'),
        ('other', 'Other')
    ], required=True)
    phone = fields.Char(related='partner_id.phone', readonly=False)
    name = fields.Char(related='partner_id.name', readonly=False)
    parent_id = fields.Many2one(related='partner_id.parent_id', readonly=False, string="Organization")
    email = fields.Char(related='parent_id.email', readonly=False)

    _sql_constraints = [('team_staff_unique', 'unique(team_id, partner_id)',
                         'Each partner can only be related to a given team once.')]

    @api.constrains('role')
    def _constrain_role(self):
        teams = self.mapped('team_id')
        for team in teams:
            if len(team.staff_ids.filtered(lambda r: r.role == 'head_coach')) > 1:
                raise ValidationError(_("A team can have only one head coach."))
            if len(team.staff_ids.filtered(lambda r: r.role == 'head_trainer')) > 1:
                raise ValidationError(_("A team can have only one head trainer."))

    @api.onchange('phone')
    def _onchange_phone_validation(self):
        if self.phone:
            self.phone = self.partner_id._phone_format(self.phone, force_format='INTERNATIONAL')