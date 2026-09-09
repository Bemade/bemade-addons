from odoo import models, fields, _, api, Command, SUPERUSER_ID
from odoo.exceptions import ValidationError, AccessError, UserError
from datetime import date, datetime, timedelta
from dateutil.relativedelta import relativedelta
from odoo.addons.phone_validation.tools import phone_validation
import logging

_logger = logging.getLogger(__name__)

external_tracking_fields = {
    "last_consultation_date",
    "match_status",
    "practice_status",
    "predicted_return_date",
    "return_date",
}

internal_tracking_fields = {
    "team_info_notes",
    "age",
    "date_of_birth",
}


class Patient(models.Model):
    _name = "sports.patient"
    _description = "Patient"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    
    _sql_constraints = [
        ('unique_patient', 'UNIQUE(partner_id)', 'A patient with this contact already exists.'),
    ]
    pending_removal = fields.Boolean(string='Pending Removal', default=False, tracking=True, 
                                    help='Indicates if this player has a pending removal request')
    _order = "last_name, first_name"
    
    active = fields.Boolean(
        string='Active',
        default=True,
        help="If unchecked, it means this patient has been archived and won't appear in searches by default.")

    # res.partner fields
    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Contact",
        ondelete="restrict",
        compute_sudo=True,
    )
    first_name = fields.Char(required=True, tracking=True)
    last_name = fields.Char(required=True, tracking=True)
    name = fields.Char(
        related="partner_id.name",
    )
    phone = fields.Char(related="partner_id.phone", readonly=False)
    mobile = fields.Char(related="partner_id.mobile", readonly=False)
    street = fields.Char(related="partner_id.street", readonly=False)
    street2 = fields.Char(related="partner_id.street2", readonly=False)
    city = fields.Char(related="partner_id.city", readonly=False)
    state_id = fields.Many2one(related="partner_id.state_id", readonly=False)
    zip = fields.Char(related="partner_id.zip", readonly=False)
    country_id = fields.Many2one(related="partner_id.country_id", readonly=False)
    email = fields.Char(related="partner_id.email", readonly=False)

    # Migration tracking field
    odoo16_patient_id = fields.Integer(
        string='Odoo 16 Patient ID',
        help='Original patient ID from Odoo 16 database for migration tracking',
        index=True
    )

    # Patient fields
    date_of_birth = fields.Date(
        groups="bemade_sports_clinic.group_sports_clinic_treatment_professional,bemade_sports_clinic.group_portal_treatment_professional",
        tracking=True,
    )
    age = fields.Integer(
        compute="_compute_age",
        groups="bemade_sports_clinic.group_sports_clinic_treatment_professional,bemade_sports_clinic.group_portal_treatment_professional",
    )
    contact_ids = fields.One2many(
        comodel_name="sports.patient.contact",
        inverse_name="patient_id",
        string="Patient Contacts",
        groups="bemade_sports_clinic.group_sports_clinic_user,bemade_sports_clinic.group_portal_treatment_professional",
    )
    team_ids = fields.Many2many(
        comodel_name="sports.team",
        relation="sports_team_patient_rel",
        column1="patient_id",
        column2="team_id",
        string="Teams",
    )
    match_status = fields.Selection(
        # Selection rather than bool for easy expansion later
        selection=[
            ("yes", "Yes"),
            ("no", "No"),
        ],
        required=True,
        default="yes",
        tracking=True,
    )
    practice_status = fields.Selection(
        selection=[("yes", "Yes"), ("no_contact", "Yes, no contact"), ("no", "No")],
        tracking=True,
        required=True,
        default="yes",
    )
    injury_ids = fields.One2many(
        comodel_name="sports.patient.injury",
        inverse_name="patient_id",
        string="Injuries",
    )
    treatment_note_ids = fields.One2many(
        comodel_name="sports.treatment.note",
        inverse_name="patient_id",
        string="Treatment Notes",
    )
    treatment_note_count = fields.Integer(
        compute="_compute_treatment_note_count",
        string="Treatment Note Count",
    )
    injured_since = fields.Date(compute="_compute_is_injured")
    predicted_return_date = fields.Date(tracking=True)
    return_date = fields.Date(
        tracking=True,
        help="When the player was cleared by medical staff to " "return to match play.",
    )
    is_injured = fields.Boolean(compute="_compute_is_injured")
    stage = fields.Selection(
        selection=[
            ("no_play", "Injured"),
            ("practice_ok", "Practice OK"),
            ("healthy", "Play OK"),
        ],
        compute="_compute_stage",
    )
    last_consultation_date = fields.Date(tracking=True)
    active_injury_count = fields.Integer(compute="_compute_active_injury_count")
    activity_count = fields.Integer(compute="_compute_activity_count")
    # Documents linked to this patient (optionally to an injury)
    document_ids = fields.One2many(
        comodel_name="sports.injury.document",
        inverse_name="patient_id",
        string="Documents",
    )
    document_count = fields.Integer(
        compute="_compute_document_count",
        string="Document Count",
    )
    allergies = fields.Text(
        groups="bemade_sports_clinic.group_sports_clinic_treatment_professional,bemade_sports_clinic.group_portal_treatment_professional",
    )
    team_info_notes = fields.Text(
        string="Notes",
        tracking=True,
        groups="bemade_sports_clinic.group_sports_clinic_treatment_professional,bemade_sports_clinic.group_portal_treatment_professional",
    )

    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if (
            "team_ids" in fields_list
            and "params" in self.env.context
            and self.env.context.get("params", {}).get("model") == "sports.team"
        ):
            team = self.env["sports.team"].browse(self.env.context.get("params")["id"])
            team_ids = [Command.set([team.id])]
            if team_ids:
                res.update({"team_ids": team_ids})
        return res

    def write(self, values):
        res = super().write(values)
        if "team_ids" in values:
            self.sudo().recompute_followers()
        if "first_name" in values or "last_name" in values:
            self._recompute_name()
        return res

    def _recompute_name(self):
        for rec in self:
            rec.partner_id.with_context(patient_update=True).name = (
                rec._get_name_from_first_and_last(rec.first_name, rec.last_name)
            )

    @api.model_create_multi
    def create(self, vals_list):
        for row in vals_list:
            if "partner_id" not in row:
                row["partner_id"] = (
                    self.env["res.partner"].with_context(
                        tracking_disable=True,
                        mail_create_nosubscribe=True,
                    )
                    .create(
                        {
                            "name": self._get_name_from_first_and_last(
                                row["first_name"], row["last_name"]
                            )
                        }
                    )
                    .id
                )
        res = super().create(vals_list)
        # Avoid triggering follower recomputation (which can create mail/follower
        # side-effects) when explicitly asked to skip, e.g., during portal creation.
        if not self.env.context.get("skip_recompute_followers"):
            res.sudo().with_context(
                tracking_disable=True,
                mail_create_nosubscribe=True,
            ).recompute_followers()
        return res

    @api.constrains("match_status", "practice_status")
    def constrain_match_and_practice_status(self):
        """Avoid invalid combinations of match and practice status:
        - Yes (match), No (practice)
        - Yes (match), No Contact (practice)
        """
        # combinations of (match_status, practice_status) that are valid
        valid_combinations = [
            ("yes", "yes"),
            ("no", "yes"),
            ("no", "no_contact"),
            ("no", "no"),
        ]
        for rec in self:
            if (rec.match_status, rec.practice_status) not in valid_combinations:
                raise ValidationError(
                    _("Invalid combination of match and practice status.")
                )

    @api.depends("injury_ids.stage")
    def _compute_active_injury_count(self):
        for rec in self:
            rec.active_injury_count = len(
                rec.injury_ids.filtered(lambda r: r.stage == "active")
            )

    @api.depends("match_status", "practice_status")
    def _compute_stage(self):
        stage_map = {
            ("yes", "yes"): "healthy",
            ("no", "yes"): "practice_ok",
            ("no", "no_contact"): "practice_ok",
            ("no", "no"): "no_play",
        }
        for rec in self:
            # not a valid combination, will be caught by constraint if save is attempted
            if (rec.match_status, rec.practice_status) not in stage_map:
                rec.stage = False
                continue
            rec.stage = stage_map[(rec.match_status, rec.practice_status)]

    @api.depends("date_of_birth")
    def _compute_age(self):
        for rec in self:
            if not rec.date_of_birth:
                rec.age = False
            else:
                rec.age = relativedelta(date.today(), rec.date_of_birth).years

    @api.model
    def _get_name_from_first_and_last(self, first_name, last_name):
        names = []
        if first_name:
            names.append(first_name)
        if last_name:
            names.append(last_name)
        return " ".join(names)

    @api.depends("practice_status", "match_status", "injury_ids.injury_date")
    def _compute_is_injured(self):
        for patient in self:
            # Patient is injured if their stage is not "healthy"
            patient.is_injured = patient.stage != "healthy"
            
            # For injured_since, find the earliest injury date from active injuries
            # This logic is kept but may not be reliable until user habits change
            if patient.is_injured:
                active_injuries = self.env["sports.patient.injury"].search(
                    [
                        ("patient_id", "=", patient.id),
                        ("stage", "=", "active"),
                    ]
                )
                if active_injuries:
                    injury_dates = [d for d in active_injuries.mapped("injury_date") if d]
                    patient.injured_since = min(injury_dates) if injury_dates else False
                else:
                    patient.injured_since = False
            else:
                patient.injured_since = False
                
    def _compute_treatment_note_count(self):
        for patient in self:
            patient.treatment_note_count = self.env['sports.treatment.note'].search_count(
                [('patient_id', '=', patient.id)]
            )

    def _compute_activity_count(self):
        for rec in self:
            rec.activity_count = self.env['mail.activity'].search_count([
                ('res_model', '=', 'sports.patient'),
                ('res_id', '=', rec.id)
            ])

    def _compute_document_count(self):
        for patient in self:
            patient.document_count = self.env['sports.injury.document'].search_count([
                ('patient_id', '=', patient.id)
            ])

    def action_view_documents(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Documents'),
            'res_model': 'sports.injury.document',
            'view_mode': 'list,form',
            'domain': [('patient_id', '=', self.id)],
            'context': {
                'default_patient_id': self.id,
            },
        }

    def action_view_patient_form(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "view_mode": "form",
            "res_model": "sports.patient",
            "res_id": self.id,
            "context": self._context,
        }

    def action_consulted_today(self):
        self.ensure_one()  # should just be called from form view
        self.last_consultation_date = date.today()
        return {
            "view_mode": "form",
            "res_model": "sports.patient",
            "context": self._context,
            "res_id": self.id,
        }
        
    def action_report_injury(self):
        """Public method to report injury with proper access checks."""
        self.ensure_one()
        
        # Check permissions - user must have access to this patient
        user = self.env.user
        if user.has_group('base.group_portal'):
            # Portal users must be staff on at least one of the patient's teams
            user_teams = user.partner_id.team_staff_rel_ids.mapped('team_id')
            patient_teams = self.team_ids
            if not (user_teams & patient_teams):
                raise AccessError(_("You don't have permission to report injuries for this patient"))
        # Backend users with appropriate groups can access any patient
        elif not (user.has_group('bemade_sports_clinic.group_sports_clinic_treatment_professional') or
                  user.has_group('bemade_sports_clinic.group_sports_clinic_admin') or
                  user.has_group('base.group_system')):
            raise AccessError(_("You don't have permission to report injuries"))
        
        # Call the private implementation
        return self._action_report_injury()
    
    def _action_report_injury(self):
        """
        Private method containing the actual sudo operations for injury reporting.
        
        :return: dict: Action result with success notification
        """
        self.ensure_one()
        is_portal = self.env.user.has_group('base.group_portal')
        
        if is_portal:
            # Redirect to portal injury form
            base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            portal_url = f"{base_url}/my/patient/injury/new?patient_id={self.id}"
            return {
                'type': 'ir.actions.act_url',
                'url': portal_url,
                'target': 'self',
            }
        else:
            # Open backend injury form
            return {
                'type': 'ir.actions.act_window',
                'name': f'Report Injury for {self.name}',
                'view_mode': 'form',
                'res_model': 'sports.patient.injury',
                'context': {
                    'default_patient_id': self.id,
                    'default_patient_name': self.name,
                    'default_stage': 'active',
                    'default_team_id': self.team_ids[0].id if self.team_ids else False
                },
            }

    @api.onchange("mobile", "country_id")
    def _onchange_mobile_validation(self):
        if self.mobile:
            self.mobile = self._phone_format(self.mobile, force_format="INTERNATIONAL")

    @api.onchange("phone", "country_id")
    def _onchange_phone_validation(self):
        if self.phone:
            self.phone = self._phone_format(self.phone, force_format="INTERNATIONAL")

    def _phone_format(self, number, force_format="E164"):
        country = self.country_id or self.env.company.country_id
        if not country or not number:
            return number
        return phone_validation.phone_format(
            number,
            country.code if country else None,
            country.phone_code if country else None,
            force_format=force_format,
            raise_exception=False,
        )

    def _track_subtype(self, init_values):
        return self.env.ref("mail.mt_note")

    def _track_template(self, changes):
        res = super()._track_template(changes)
        params = set(changes)
        external = bool(external_tracking_fields & params)
        if external:
            first_external_field = (external_tracking_fields & params).pop()
            res[first_external_field] = (
                self.env.ref(
                    "bemade_sports_clinic.mail_template_patient_status_update"
                ),
                {
                    "auto_delete": False,
                    "subtype_id": self.env.ref(
                        "bemade_sports_clinic.subtype_patient_external_update"
                    ).id,
                    "email_layout_xmlid": "mail.mail_notification_light",
                },
            )
        # Tracking removed from team_info_notes HTML field as it's not supported by the mail tracking system
        # if "team_info_notes" in changes:
        #     res["team_info_notes"] = (
        #         self.env.ref(
        #             "bemade_sports_clinic.mail_template_patient_new_team_note"
        #         ),
        #         {
        #             "auto_delete": False,
        #             "subtype_id": self.env.ref(
        #                 "bemade_sports_clinic.subtype_patient_internal_update"
        #             ).id,
        #             "email_layout_xmlid": "mail.mail_notification_light",
        #         },
        #     )
        return res
        
    def _get_team_head_therapist_user(self, team):
        """Get the head therapist user for a team, or None if not found"""
        head_therapist = team.staff_ids.filtered(
            lambda s: s.role == 'head_therapist' and s.user_ids
        )
        if head_therapist:
            return head_therapist.user_ids[0]
        return None
        
    def _get_admin_user(self):
        """Get the admin user with the lowest ID"""
        return self.env['res.users'].search([('active', '=', True)], order='id', limit=1)
    
    def request_team_removal(self, team_id, reason=None):
        """Public method to request team removal with proper access checks."""
        self.ensure_one()
        team = self.env['sports.team'].browse(team_id)
        
        # Get current user and check permissions
        current_user = self.env.user
        is_admin = current_user.has_group('base.group_system')
        
        # Permission check - do this before team membership validation
        if not is_admin:
            # Check if user is staff on the team
            user_staff_roles = team.staff_ids.filtered(
                lambda s: s.user_ids and current_user.id in s.user_ids.ids
            )
            if not user_staff_roles:
                raise AccessError(_(
                    "You don't have permission to request removal for this team. "
                    "Only team staff or administrators can request player removal."
                ))
        
        # Validate team existence and membership
        if not team.exists():
            raise ValidationError(_("Team not found or you don't have access to it"))
            
        if team not in self.team_ids:
            raise ValidationError(_("Player is not a member of the specified team"))
        
        # Call the private implementation
        return self._request_team_removal(team_id, reason)
    
    def _request_team_removal(self, team_id, reason=None):
        """
        Private method containing the actual sudo operations for requesting team removal.
        The actual activity creation will be handled by the scheduled action.
        
        :param int team_id: ID of the team to request removal from
        :param str reason: Optional reason for the removal request
        :return: dict: Action result with success notification
        """
        self.ensure_one()
        team = self.env['sports.team'].browse(team_id)
        current_user = self.env.user
        
        # Set the pending_removal flag
        self.write({'pending_removal': True})
        
        # Log the request with details
        log_message = _(
            "Removal request submitted for player %(player)s from team %(team)s by %(user)s"
        ) % {
            'player': self.display_name,
            'team': team.name,
            'user': current_user.name
        }
        
        if reason:
            log_message += _("\nReason: %s") % reason
            
        # Log the request in the chatter
        self.sudo().message_post(body=log_message)
        
        # Return success notification
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Removal Request Submitted'),
                'message': _('Your removal request has been submitted and will be processed by an administrator.'),
                'type': 'success',
                'sticky': True,
            }
        }
        
    def _schedule_removal_request_activity(self, request_data):
        """
        Scheduled action to create an activity for the head therapist to review the removal request.
        
        :param dict request_data: Data for the removal request
        """
        player = self.env['sports.patient'].browse(request_data['player_id'])
        team = self.env['sports.team'].browse(request_data['team_id'])
        requested_by = self.env['res.users'].browse(request_data['requested_by_id'])
        reason = request_data['reason']
        is_last_team = request_data['is_last_team']
        assignee = self.env['res.users'].browse(request_data['assignee_id'])
        
        # Create a more detailed activity
        note = _("Player Removal Request\n")
        note += _("====================\n\n")
        note += _("Player: %s\n") % player.display_name
        note += _("Team: %s\n") % team.name
        note += _("Requested by: %s\n\n") % requested_by.name
        
        if reason:
            note += _("Reason for removal request:\n%s\n\n") % reason
            
        if is_last_team:
            note += _("⚠️ WARNING: This is the player's only team. They will be archived if removed.\n\n")
            
        note += _("Please review this request and take appropriate action.")
        
        # Create activity for head therapist
        activity_vals = {
            'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
            'note': note,
            'res_id': player.id,
            'res_model_id': self.env['ir.model']._get('sports.patient').id,
            'user_id': assignee.id,
            'summary': _('Player Removal Request: %s') % player.display_name,
        }
        
        # Create the activity
        self.env['mail.activity'].create(activity_vals)
    

    
    @api.model
    def _cron_handle_pending_removals(self):
        """
        Scheduled action to handle players pending removal.
        Creates mail activities for head therapists to review the removal requests.
        """
        # Find all active players with pending removal that still have teams
        players_pending_removal = self.search([
            ('active', '=', True),
            ('pending_removal', '=', True),
            ('team_ids', '!=', False)
        ])
        
        if not players_pending_removal:
            return
            
        # Get the mail activity type
        activity_type = self.env.ref('mail.mail_activity_data_todo')
        model_id = self.env['ir.model']._get('sports.patient').id
        today = fields.Date.today()
        
        for player in players_pending_removal:
            # Skip if there's already an activity for this player
            existing_activity = self.env['mail.activity'].search([
                ('res_model', '=', 'sports.patient'),
                ('res_id', '=', player.id),
                ('activity_type_id', '=', activity_type.id),
                ('summary', 'ilike', 'Player Removal Request')
            ], limit=1)
            
            if existing_activity:
                continue
                
            # Find head therapist (role == 'head_therapist') or fallback to any therapist
            team = player.team_ids[0]
            staff = team.staff_ids
            head_therapist = staff.filtered(lambda s: s.role == 'head_therapist' and s.user_ids)
            if not head_therapist:
                # Fallback to any therapist with a linked user
                head_therapist = staff.filtered(lambda s: s.role == 'therapist' and s.user_ids)

            user_id = SUPERUSER_ID
            if head_therapist:
                # pick first linked user id
                user_id = head_therapist.user_ids[0].id
            
            # Create the activity
            self.env['mail.activity'].create({
                'activity_type_id': activity_type.id,
                'summary': _('Player Removal Request'),
                'note': _('Player %s has been requested for removal from the team. Please review.') % player.display_name,
                'user_id': user_id,
                'res_id': player.id,
                'res_model_id': model_id,
                'date_deadline': today,
            })
    
    @api.model
    def _cron_archive_players_without_teams(self):
        """
        Scheduled action to archive players who have no teams.
        This is a separate process from the removal request workflow.
        """
        # Find all active players with no teams
        players_to_archive = self.search([
            ('active', '=', True),
            ('team_ids', '=', False)
        ])
        
        if players_to_archive:
            players_to_archive.write({'active': False})
            _logger.info('Archived %s players with no teams', len(players_to_archive))
    
    def _archive_if_no_teams(self, team_name, user_name):
        """
        Check if the patient has no teams left and should be archived.
        
        :param str team_name: Name of the team the patient was removed from
        :param str user_name: Name of the user performing the action
        :return: tuple: (should_archive, message)
        """
        if not self.team_ids:
            return True, _("Removed from last team %s. Player will be archived shortly.") % team_name
        return False, _("Removed from team %s by %s") % (team_name, user_name)

    def remove_from_team(self, team_id, clear_pending=True, reason=None):
        """
        Public method to remove player from team with proper permission checks.
        
        Permissions:
        - System Administrators (base.group_system) can remove any player
        - Treatment Professionals (group_sports_clinic_treatment_professional) can remove players from teams where they are therapists
        
        :param int team_id: ID of the team to remove the player from
        :param bool clear_pending: Whether to clear the pending_removal flag (default: True)
        :param str reason: Optional reason for removal (for audit purposes)
        :return: dict: Action result with success notification
        :raises ValidationError: If team is not found or player is not a member
        :raises AccessError: If user doesn't have permission to remove the player
        """
        self.ensure_one()
        team = self.env['sports.team'].browse(team_id)
        
        # Get current user and check permissions first
        current_user = self.env.user
        is_admin = current_user.has_group('base.group_system')
        
        # Check if user is a treatment professional on the team
        user_staff_roles = team.staff_ids.filtered(
            lambda s: s.user_ids and current_user.id in s.user_ids.ids
        )
        is_team_therapist = any(role.role == 'therapist' for role in user_staff_roles)
        is_treatment_prof = current_user.has_group('bemade_sports_clinic.group_sports_clinic_treatment_professional')
        
        # Permission check - do this before team membership validation
        if not is_admin:
            if not is_treatment_prof:
                raise AccessError(_(
                    "You don't have permission to remove players from teams. "
                    "Only treatment professionals or administrators can perform this action. "
                    "Please use the 'Request Removal' action instead."
                ))
            if not is_team_therapist:
                raise AccessError(_(
                    "You must be a therapist on the team to remove players. "
                    "Please request removal through the team's head therapist."
                ))
        
        # Now validate team existence and membership
        if not team.exists():
            raise ValidationError(_("Team not found or you don't have access to it"))
            
        if team not in self.team_ids:
            raise ValidationError(_("Player is not a member of the specified team"))
        
        # Call the private implementation
        return self._remove_from_team(team_id, clear_pending, reason)
    
    def _remove_from_team(self, team_id, clear_pending=True, reason=None):
        """
        Private method containing the actual sudo operations for team removal.
        
        :param int team_id: ID of the team to remove the player from
        :param bool clear_pending: Whether to clear the pending_removal flag (default: True)
        :param str reason: Optional reason for removal (for audit purposes)
        :return: dict: Action result with success notification
        """
        self.ensure_one()
        team = self.env['sports.team'].browse(team_id)
        current_user = self.env.user
        
        # Log the action with details
        log_message = _(
            "Player %(player)s removed from team %(team)s by %(user)s"
        ) % {
            'player': self.sudo().display_name,
            'team': team.sudo().name,
            'user': current_user.sudo().name
        }
        
        if reason:
            log_message += _("\nReason: %s") % reason
            
        # Prepare update values
        update_vals = {'team_ids': [(3, team.id)]}
        if clear_pending and self.sudo().pending_removal:
            update_vals['pending_removal'] = False
            log_message += _("\nPending removal flag was cleared.")
        
        # Execute the removal
        self.write(update_vals)
        
        # Check if this was the last team. After removing the last team the
        # patient is teamless, so the per-record ir.rule no longer grants the
        # portal user read access to it -> read via sudo() (task 640 follow-up).
        should_archive, archive_message = self.sudo()._archive_if_no_teams(team.name, current_user.name)
        if should_archive:
            log_message += "\n" + archive_message
            # The archiving cron job will handle this
            success_message = _('Player successfully removed from team. They will be archived shortly.')
        else:
            # Only set pending_removal if clear_pending is False and not already set
            if not clear_pending and not self.pending_removal:
                self.write({'pending_removal': True})
                log_message += _("\nPending removal flag was set for the removal request workflow.")
                success_message = _('Player successfully removed from team. A removal request has been created.')
            else:
                success_message = _('Player successfully removed from team.')
        
        # Log the action in the chatter
        # Use sudo() to avoid mail system access limitations for portal users
        self.sudo().message_post(
            body=log_message,
            message_type="comment",
            subtype_xmlid="mail.mt_comment",
        )
        
        # Return success notification
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Player Removed'),
                'message': success_message,
                'type': 'success',
                'sticky': True,
            }
        }

    @api.model
    def create_portal_patient(self, vals):
        """Public method to create a patient from portal with proper permission checks.
        
        :param dict vals: Values for patient creation including:
            - first_name (required)
            - last_name (required)
            - email (optional)
            - phone (optional)
            - team_ids (optional)
            - date_of_birth (optional)
        :return: Created patient record
        """
        # Validate required fields
        if not vals.get('first_name') or not vals.get('last_name'):
            raise ValidationError(_("First name and last name are required"))
            
        # Check permissions - must be portal treatment professional or team coach
        user = self.env.user
        if not (user.has_group('bemade_sports_clinic.group_portal_treatment_professional') or 
                user.has_group('bemade_sports_clinic.group_portal_team_coach')):
            raise AccessError(_("You don't have permission to create patients"))
        
        # Call the private implementation
        return self._create_portal_patient(vals)
    
    @api.model
    def _create_portal_patient(self, vals):
        """Private method containing the actual @api.model operations for patient creation.
        
        This method is designed to be called from portal controllers where
        portal users need to create patients but might not have direct create
        permissions on res.partner.
        
        :param dict vals: Values for patient creation
        :return: Created patient record
        """
        # Create partner first
        partner_vals = {
            'name': f"{vals['first_name']} {vals['last_name']}",
            'email': vals.get('email', False),
            'phone': vals.get('phone', False),
            'type': 'contact',
        }
        # Optional address fields coming from portal form
        # These are res.partner fields, so capture them here
        for key in ['street', 'street2', 'city', 'zip']:
            if key in vals:
                partner_vals[key] = vals.get(key) or False
        if vals.get('state_id'):
            partner_vals['state_id'] = vals.get('state_id')
        if vals.get('country_id'):
            partner_vals['country_id'] = vals.get('country_id')
        partner = (
            self.env['res.partner']
            .sudo()
            .with_context(tracking_disable=True, mail_create_nosubscribe=True)
            .create(partner_vals)
        )
        
        # Prepare patient values
        patient_vals = {
            'partner_id': partner.id,
            'first_name': vals['first_name'],
            'last_name': vals['last_name'],
        }
        
        # Optional fields
        if 'team_ids' in vals:
            patient_vals['team_ids'] = vals['team_ids']
        if 'date_of_birth' in vals and vals['date_of_birth']:
            patient_vals['date_of_birth'] = vals['date_of_birth']
        # Status fields from portal (treatment professionals only)
        if vals.get('match_status'):
            patient_vals['match_status'] = vals.get('match_status')
        if vals.get('practice_status'):
            patient_vals['practice_status'] = vals.get('practice_status')
        # Other optional patient fields
        if 'allergies' in vals:
            patient_vals['allergies'] = vals.get('allergies') or False
        if 'team_info_notes' in vals:
            patient_vals['team_info_notes'] = vals.get('team_info_notes') or False
        
        # Create patient with tracking disabled to avoid triggering mail/report side-effects
        # Also disable auto-subscriptions on creation
        patient = self.sudo().with_context(
            tracking_disable=True,
            mail_create_nosubscribe=True,
            skip_recompute_followers=True,
        ).create(patient_vals)

        # Optionally recompute followers immediately if explicitly requested by context.
        # Disabled by default for portal flows to avoid mail/report side-effects (e.g., ir.actions.report ACL reads).
        if self.env.context.get('portal_recompute_followers_post_create'):
            patient.sudo().with_context(
                tracking_disable=True,
                mail_create_nosubscribe=True,
            ).recompute_followers()

        return patient

    def recompute_followers(self):
        """Recompute the followers for this patient (and its injuries) based on the
        changes to a specific team's staff members. Ignoring manually unsubscribed
        followers, the set of followers should be the set of staff on all teams the
        patient is part of."""
        for patient in self:
            patient = patient.sudo()
            current_followers = patient.message_partner_ids
            future_followers = patient.team_ids.mapped("staff_ids").filtered(
                lambda s: not s.silent_notifications
            ).mapped("partner_id")
            removed_followers = current_followers - future_followers

            # Run follower subscribe/unsubscribe operations in a silent mail context
            silent_patient = patient.with_context(
                tracking_disable=True,
                mail_create_nolog=True,
                mail_create_nosubscribe=True,
                mail_auto_subscribe_no_notify=True,
                mail_notify_force_send=False,
            )
            silent_injuries = patient.injury_ids.with_context(
                tracking_disable=True,
                mail_create_nolog=True,
                mail_create_nosubscribe=True,
                mail_auto_subscribe_no_notify=True,
                mail_notify_force_send=False,
            )

            if removed_followers:
                silent_patient.message_unsubscribe(removed_followers.ids)
                silent_injuries.message_unsubscribe(removed_followers.ids)
            if future_followers:
                silent_patient.message_subscribe(future_followers.ids)
                silent_injuries.message_subscribe(future_followers.ids)
