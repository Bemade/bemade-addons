from odoo import models, fields, api, _, Command
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
    head_therapist_id = fields.Many2one(comodel_name='res.partner',
                                      compute='_compute_head_therapist',
                                      store=True)
    head_therapist_name = fields.Char(related='head_therapist_id.name')
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
    def _compute_head_therapist(self):
        for rec in self:
            staff = rec.staff_ids.filtered(lambda r: r.role == 'head_therapist')
            rec.head_therapist_id = staff.partner_id if staff else False


class TeamStaff(models.Model):
    _name = "sports.team.staff"
    _description = "Sports Team Staff"

    sequence = fields.Integer()
    team_id = fields.Many2one(comodel_name='sports.team', string='Team', required=True)
    partner_id = fields.Many2one(comodel_name='res.partner', string='Staff Member',
                                 required=True, domain=[('is_company', '=', False)])
    role = fields.Selection(selection=[
        ('head_coach', 'Head Coach'),
        ('head_therapist', 'Head Therapist'),
        ('coach', 'Coach'),
        ('therapist', 'Therapist'),
        ('doctor', 'Doctor'),
        ('other', 'Other')
    ], required=True)
    mobile = fields.Char(related='partner_id.mobile', readonly=False)
    name = fields.Char(related='partner_id.name', readonly=False)
    parent_id = fields.Many2one(related='partner_id.parent_id', readonly=False, string="Organization",
                                domain=[('is_company', '=', True)])
    email = fields.Char(related='partner_id.email', readonly=False)
    user_ids = fields.One2many(related='partner_id.user_ids', readonly=True)
    has_portal_access = fields.Boolean(compute='_compute_has_portal_access', compute_sudo=True)

    _sql_constraints = [('team_staff_unique', 'unique(team_id, partner_id)',
                         'Each partner can only be related to a given team once.')]

    @api.constrains('role')
    def _constrain_role(self):
        teams = self.mapped('team_id')
        for team in teams:
            if len(team.staff_ids.filtered(lambda r: r.role == 'head_coach')) > 1:
                raise ValidationError(_("A team can have only one head coach."))
            if len(team.staff_ids.filtered(lambda r: r.role == 'head_therapist')) > 1:
                raise ValidationError(_("A team can have only one head therapist."))

    @api.onchange('mobile')
    def _onchange_mobile_validation(self):
        if self.mobile:
            self.mobile = self.partner_id._phone_format(self.mobile, force_format='INTERNATIONAL')

    @api.depends('user_ids', 'user_ids.groups_id')
    def _compute_has_portal_access(self):
        for rec in self:
            rec.has_portal_access = bool(rec.user_ids.filtered(lambda r: r.has_group('base.group_portal'))) or bool(
                rec.user_ids.filtered(lambda r: r.has_group('base.group_user'))) or bool(rec.partner_id.signup_token)

    def action_revoke_portal_access(self):
        group_portal = self.env.ref('base.group_portal')
        group_public = self.env.ref('base.group_public')
        self.user_ids.write(
            {'groups_id': [Command.unlink(group_portal.id), Command.link(group_public.id)], 'active': False})
        # Remove the signup token, so it cannot be used
        self.partner_id.sudo().signup_token = False

    def action_grant_portal_access(self):
        wiz = self.env['portal.wizard'].create({'partner_ids': [(4, self.partner_id.id)]})
        return wiz._action_open_modal()
