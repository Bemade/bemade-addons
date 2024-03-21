from odoo import models, fields, _, api, Command
from odoo.exceptions import ValidationError
from datetime import date
from dateutil.relativedelta import relativedelta
from odoo.addons.phone_validation.tools import phone_validation
from typing import Set, Tuple

external_tracking_fields = {
    'last_consultation_date',
    'match_status',
    'practice_status',
    'predicted_return_date',
    'return_date',
}

internal_tracking_fields = {
    'team_info_notes',
    'age',
    'date_of_birth',
}


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
    age = fields.Integer(
        compute='_compute_age',
        groups="bemade_sports_clinic.group_sports_clinic_treatment_professional"
    )
    contact_ids = fields.One2many(
        comodel_name='sports.patient.contact',
        inverse_name='patient_id',
        string='Patient Contacts',
        groups="bemade_sports_clinic.group_sports_clinic_user"
    )
    team_ids = fields.Many2many(
        comodel_name='sports.team',
        relation='sports_team_patient_rel',
        column1='patient_id',
        column2='team_id',
        string='Teams',
    )
    match_status = fields.Selection(  # Selection rather than bool for easy expansion later
        selection=[
            ('yes', 'Yes'),
            ('no', 'No'),
        ],
        required=True,
        default='yes',
        tracking=True)
    practice_status = fields.Selection(
        selection=[
            ('yes', 'Yes'),
            ('no_contact', 'Yes, no contact'),
            ('no', 'No')
        ],
        tracking=True,
        required=True,
        default='yes',
    )
    injury_ids = fields.One2many(
        comodel_name='sports.patient.injury',
        inverse_name='patient_id',
        string='Injuries',
    )
    injured_since = fields.Date(compute='_compute_is_injured')
    predicted_return_date = fields.Date(tracking=True)
    return_date = fields.Date(
        tracking=True,
        help="When the player was cleared by medical staff to "
             "return to match play."
    )
    is_injured = fields.Boolean(compute="_compute_is_injured")
    stage = fields.Selection(
        selection=[
            ('no_play', 'Injured'),
            ('practice_ok', 'Practice OK'),
            ('healthy', 'Play OK')
        ],
        compute='_compute_stage')
    last_consultation_date = fields.Date(tracking=True)
    active_injury_count = fields.Integer(compute='_compute_active_injury_count')
    allergies = fields.Text()
    team_info_notes = fields.Html(
        string="Notes",
        tracking=True,
    )

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

    def _track_subtype(self, init_values):
        return self.env.ref('mail.mt_note')

    def _track_template(self, changes):
        res = super()._track_template(changes)
        params = set(changes)
        external = bool(external_tracking_fields & params)
        if external:
            first_external_field = (external_tracking_fields & params).pop()
            res[first_external_field] = (
                self.env.ref('bemade_sports_clinic.mail_template_patient_status_update'), {
                    'auto_delete_message': False,
                    'subtype_id': self.env.ref('bemade_sports_clinic.subtype_patient_external_update').id,
                    'email_layout_xmlid': 'mail.mail_notification_light',
                }
            )
        if 'team_info_notes' in changes:
            res['team_info_notes'] = (
                self.env.ref('bemade_sports_clinic.mail_template_patient_new_internal_note'), {
                    'auto_delete_message': False,
                    'subtype_id': self.env.ref('bemade_sports_clinic.subtype_patient_internal_update').id,
                    'email_layout_xmlid': 'mail.mail_notification_light',
                }
            )
        return res
