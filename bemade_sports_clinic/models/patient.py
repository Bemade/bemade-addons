from odoo import models, fields, _, api, Command
from odoo.exceptions import ValidationError
from datetime import date
from dateutil.relativedelta import relativedelta
from odoo.addons.phone_validation.tools import phone_validation


class Patient(models.Model):
    _name = 'sports.patient'
    _description = "Patient"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'last_name, first_name'

    # res.partner fields
    partner_id = fields.Many2one(comodel_name='res.partner', string='Contact', ondelete='restrict', compute_sudo=True)
    first_name = fields.Char(required=True, tracking=True)
    last_name = fields.Char(required=True, tracking=True)
    name = fields.Char(related='partner_id.name', compute="_compute_name", compute_sudo=True)
    phone = fields.Char(related='partner_id.phone', readonly=False)
    mobile = fields.Char(related='partner_id.mobile', readonly=False)
    street = fields.Char(related='partner_id.street', readonly=False)
    street2 = fields.Char(related='partner_id.street2', readonly=False)
    city = fields.Char(related='partner_id.city', readonly=False)
    state_id = fields.Many2one(related='partner_id.state_id', readonly=False)
    zip = fields.Char(related='partner_id.zip', readonly=False)
    country_id = fields.Many2one(related='partner_id.country_id', readonly=False)
    email = fields.Char(related='partner_id.email', readonly=False)

    # Patient fields
    date_of_birth = fields.Date(
        groups="bemade_sports_clinic.group_sports_clinic_treatment_professional",
        tracking=True)
    age = fields.Integer(compute='_compute_age',
                         groups="bemade_sports_clinic.group_sports_clinic_treatment_professional",
                         tracking=True)
    contact_ids = fields.One2many(comodel_name='sports.patient.contact',
                                  inverse_name='patient_id',
                                  string='Patient Contacts',
                                  groups="bemade_sports_clinic.group_sports_clinic_user")
    team_ids = fields.Many2many(comodel_name='sports.team',
                                relation='sports_team_patient_rel',
                                column1='patient_id',
                                column2='team_id',
                                string='Teams', )
    match_status = fields.Selection([  # Selection for easy expansion later
        ('yes', 'Yes'),
        ('no', 'No'),
    ], required=True, default='yes', tracking=True)
    practice_status = fields.Selection([
        ('yes', 'Yes'),
        ('no_contact', 'Yes, no contact'),
        ('no', 'No')], tracking=True, required=True, default='yes')

    injury_ids = fields.One2many(comodel_name='sports.patient.injury',
                                 inverse_name='patient_id',
                                 string='Injuries', )
    injured_since = fields.Date(compute='_compute_is_injured')
    predicted_return_date = fields.Date(tracking=True)
    return_date = fields.Date(tracking=True,
                              help="When the player was cleared by medical staff to "
                                   "return to match play.")
    is_injured = fields.Boolean(compute="_compute_is_injured")
    stage = fields.Selection(
        selection=[('no_play', 'Injured'), ('practice_ok', 'Practice OK'), ('healthy', 'Play OK')],
        compute='_compute_stage')
    last_consultation_date = fields.Date()
    active_injury_count = fields.Integer(compute='_compute_active_injury_count')
    allergies = fields.Text()
    team_info_notes = fields.Html(string="Notes")

    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if 'team_ids' in fields_list and 'params' in self.env.context \
                and self.env.context.get('params')['model'] == 'sports.team':
            team = self.env['sports.team'].browse(self.env.context.get('params')['id'])
            team_ids = [Command.set([team.id])]
            if team_ids:
                res.update({'team_ids': team_ids})
        return res

    @api.model_create_multi
    def create(self, vals_list):
        for row in vals_list:
            if 'partner_id' not in row:
                row['partner_id'] = self.env['res.partner'].create({
                    'name': self._get_name_from_first_and_last(row['first_name'], row['last_name'])
                }).id
        return super().create(vals_list)

    @api.constrains('match_status', 'practice_status')
    def constrain_match_and_practice_status(self):
        """ Avoid invalid combinations of match and practice status:
                - Yes (match), No (practice)
                - Yes (match), No Contact (practice)
        """
        # combinations of (match_status, practice_status) that are valid
        valid_combinations = [('yes', 'yes'), ('no', 'yes'), ('no', 'no_contact'), ('no', 'no')]
        for rec in self:
            if (rec.match_status, rec.practice_status) not in valid_combinations:
                raise ValidationError(_("Invalid combination of match and practice status."))

    @api.depends('injury_ids.stage')
    def _compute_active_injury_count(self):
        for rec in self:
            rec.active_injury_count = len(rec.injury_ids.filtered(lambda r: r.stage == 'active'))

    @api.depends('match_status', 'practice_status')
    def _compute_stage(self):
        stage_map = {
            ('yes', 'yes'): 'healthy',
            ('no', 'yes'): 'practice_ok',
            ('no', 'no_contact'): 'practice_ok',
            ('no', 'no'): 'no_play',
        }
        for rec in self:
            if (rec.match_status, rec.practice_status) not in stage_map:
                rec.stage = False  # not a valid combination, will be caught by constraint if save is attempted
                continue
            rec.stage = stage_map[(rec.match_status, rec.practice_status)]

    @api.depends('date_of_birth')
    def _compute_age(self):
        for rec in self:
            if not rec.date_of_birth:
                rec.age = False
            else:
                rec.age = relativedelta(date.today(), rec.date_of_birth).years

    @api.depends('first_name', 'last_name')
    def _compute_name(self):
        for rec in self:
            rec.name = self._get_name_from_first_and_last(rec.first_name, rec.last_name)

    @api.model
    def _get_name_from_first_and_last(self, first_name, last_name):
        return ((first_name or "") + " " + (last_name or "")).strip()

    @api.depends('practice_status', 'match_status', 'injury_ids.injury_date')
    def _compute_is_injured(self):
        for rec in self:
            rec.is_injured = rec.practice_status != 'yes' or rec.match_status != 'yes'
            if rec.is_injured:
                unresolved_injuries = rec.injury_ids.filtered(lambda r: not r.stage == 'resolved')
                rec.injured_since = unresolved_injuries and unresolved_injuries[0].injury_date
            else:
                rec.injured_since = False

    def action_view_patient_form(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'sports.patient',
            'res_id': self.id,
            'context': self._context,
        }

    def action_consulted_today(self):
        self.ensure_one()  # should just be called from form view
        self.last_consultation_date = date.today()
        return {
            'view_mode': 'form',
            'res_model': 'sports.patient',
            'context': self._context,
            'res_id': self.id,
        }

    @api.onchange('mobile', 'country_id')
    def _onchange_mobile_validation(self):
        if self.mobile:
            self.mobile = self._phone_format(self.mobile, force_format="INTERNATIONAL")

    @api.onchange('phone', 'country_id')
    def _onchange_phone_validation(self):
        if self.phone:
            self.phone = self._phone_format(self.phone, force_format="INTERNATIONAL")

    def _phone_format(self, number, force_format='E164'):
        country = self.country_id or self.env.company.country_id
        if not country or not number:
            return number
        return phone_validation.phone_format(
            number,
            country.code if country else None,
            country.phone_code if country else None,
            force_format=force_format,
            raise_exception=False
        )


class PatientContact(models.Model):
    _name = 'sports.patient.contact'
    _description = "Emergency or other contacts for a patient."

    sequence = fields.Integer(required=True, default=0)
    name = fields.Char(unaccent=False)
    contact_type = fields.Selection(selection=[
        ('mother', 'Mother'),
        ('father', 'Father'),
        ('other', 'Other'),
    ], required=True)
    mobile = fields.Char(unaccent=False, required=True)
    patient_id = fields.Many2one(comodel_name='sports.patient', string='Patient')

    @api.onchange('mobile')
    def _onchange_mobile_validation(self):
        if self.mobile:
            self.mobile = self._phone_format(self.mobile, force_format="INTERNATIONAL")

    def _phone_format(self, number, force_format='E164'):
        country = self.patient_id.country_id or self.env.company.country_id
        if not country or not number:
            return number
        return phone_validation.phone_format(
            number,
            country.code if country else None,
            country.phone_code if country else None,
            force_format=force_format,
            raise_exception=False
        )


class PatientInjury(models.Model):
    _name = 'sports.patient.injury'
    _description = "Patient Injury"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'diagnosis'

    patient_id = fields.Many2one(comodel_name='sports.patient',
                                 string="Patient",
                                 readonly=True,
                                 required=True)
    patient_name = fields.Char(related="patient_id.name")
    diagnosis = fields.Char(tracking=True)
    injury_date = fields.Date(string='Date of Injury',
                              default=date.today())
    injury_date_na = fields.Boolean(string="N/A", default=False)
    internal_notes = fields.Html(tracking=True)
    external_notes = fields.Html(tracking=True)
    treatment_professional_ids = fields.Many2many(comodel_name='res.users',
                                                  relation='patient_injury_treatment_pro_rel',
                                                  column1='patient_injury_id',
                                                  column2='treatment_pro_id', string='Treatment Professionals',
                                                  domain=[
                                                      ('is_treatment_professional', '=',
                                                       True)], tracking=True)
    predicted_resolution_date = fields.Date(tracking=True)
    resolution_date = fields.Date(tracking=True,
                                  help="The date when the injury was actually resolved.")
    stage = fields.Selection(selection=[('active', 'Active'), ('resolved', 'Resolved')], compute='_compute_stage')

    @api.constrains('injury_date_na', 'injury_date')
    def constrain_date_blank_only_if_na(self):
        for rec in self:
            if not rec.injury_date_na and not rec.injury_date:
                raise ValidationError(_("If injury date is not set, the N/A box must be checked."))

    @api.onchange('injury_date_na')
    def _onchange_injury_date_na(self):
        for rec in self:
            if rec.injury_date_na:
                rec.injury_date = None

    @api.onchange('injury_date')
    def _onchange_injury_date(self):
        for rec in self:
            if rec.injury_date:
                rec.injury_date_na = False

    @api.depends('resolution_date')
    def _compute_stage(self):
        for rec in self:
            if rec.resolution_date and rec.resolution_date <= date.today():
                rec.stage = 'resolved'
            else:
                rec.stage = 'active'

    def write(self, vals):
        super().write(vals)
        if 'treatment_professional_ids' in vals:
            to_subscribe = (self.treatment_professional_ids.mapped('partner_id')
                            - self.message_follower_ids.mapped('partner_id'))
            self.message_subscribe(to_subscribe.ids)

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        for rec in res:
            to_subscribe = (rec.treatment_professional_ids.mapped('partner_id')
                            - rec.message_follower_ids.mapped('partner_id'))
            rec.message_subscribe(to_subscribe.ids)
        return res

    def action_view_injury_form(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'sports.patient.injury',
            'res_id': self.id,
            'context': self._context,
        }
