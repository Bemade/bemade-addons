from odoo import models, fields, api, _
from datetime import datetime, date
import pytz
from odoo.exceptions import ValidationError
from typing import Set, Tuple

external_tracking_fields = {
    'diagnosis',
    'predicted_resolution_date',
    'resolution_date',
    'external_notes',
}

# Include only fields not already included in external_tracking_fields here
internal_tracking_fields = {
    'internal_notes',
    'parental_consent',
}


class PatientInjury(models.Model):
    _name = 'sports.patient.injury'
    _description = "Patient Injury"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'diagnosis'

    @api.model
    def _today(self):
        """Get the current date in the user's time zone."""
        return datetime.now(pytz.timezone(self.env.user.tz or 'GMT'))

    # TODO: Find a way to improve notifications send about tracking injury details
    # TODO: Add field consentement_parental = fields.Selection(oui, non, non-applicable)

    patient_id = fields.Many2one(
        comodel_name='sports.patient',
        string="Patient",
        readonly=True,
        required=True
    )
    patient_name = fields.Char(related="patient_id.name")
    diagnosis = fields.Char(tracking=True)

    injury_date = fields.Date(
        string='Date of Injury',
        default=_today,
    )
    injury_date_na = fields.Boolean(string="N/A", default=False)
    internal_notes = fields.Html(tracking=True)
    external_notes = fields.Html(tracking=True)
    treatment_professional_ids = fields.Many2many(
        comodel_name='res.users',
        relation='patient_injury_treatment_pro_rel',
        column1='patient_injury_id',
        column2='treatment_pro_id', string='Treatment Professionals',
        domain=[
            ('is_treatment_professional', '=',
             True)], tracking=True
    )
    predicted_resolution_date = fields.Date(tracking=True)
    resolution_date = fields.Date(
        tracking=True,
        help="The date when the injury was actually resolved."
    )
    stage = fields.Selection(selection=[('active', 'Active'), ('resolved', 'Resolved')], compute='_compute_stage')
    parental_consent = fields.Selection(
        string="Consent for Disclosure to Parent",
        selection=[
            ('yes', 'Yes'),
            ('no', 'No'),
            ('na', 'N/A')
        ],
        help="Whether the patient has given their consent to share injury details with their parents.",
        tracking=True,
    )

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

    def _track_subtype(self, init_values):
        return self.env.ref('mail.mt_note')

    def _track_template(self, changes):
        res = super()._track_template(changes)
        params = set(changes)
        external = bool(external_tracking_fields & params)
        if external:
            first_external_field = (external_tracking_fields & params).pop()
            res[first_external_field] = (
                self.env.ref('bemade_sports_clinic.mail_template_patient_injury_status_update'), {
                    'auto_delete_message': False,
                    'subtype_id': self.env.ref('bemade_sports_clinic.subtype_patient_injury_external_update').id,
                    'email_layout_xmlid': 'mail.mail_notification_light',
                }
            )
        if 'internal_notes' in changes:
            res['internal_notes'] = (
                self.env.ref('bemade_sports_clinic.mail_template_patient_injury_new_internal_note'), {
                    'auto_delete_message': False,
                    'subtype_id': self.env.ref('bemade_sports_clinic.subtype_patient_injury_internal_update').id,
                    'email_layout_xmlid': 'mail.mail_notification_light',
                }
            )
        return res
