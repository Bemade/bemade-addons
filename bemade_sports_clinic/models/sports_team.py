from odoo import models, fields, api, _, Command
from odoo.exceptions import ValidationError
import logging


_logger = logging.getLogger(__name__)


class SportsTeam(models.Model):
    _name = "sports.team"
    _description = "Sports Team"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    name = fields.Char()
    event_ids = fields.Many2many(
        comodel_name="sports.event",
        relation="sports_event_team_rel",
        column1="team_id",
        column2="event_id",
        string="Events",
    )
    patient_ids = fields.Many2many(
        comodel_name="sports.patient",
        relation="sports_team_patient_rel",
        column1="team_id",
        column2="patient_id",
        string="Players",
        tracking=True,
    )
    player_count = fields.Integer(compute="_compute_player_counts")
    injured_count = fields.Integer(compute="_compute_player_counts")
    healthy_count = fields.Integer(compute="_compute_player_counts")
    activity_count = fields.Integer(compute="_compute_activity_count")
    parent_id = fields.Many2one(
        comodel_name="res.partner",
        string="Parent Organization",
        ondelete="restrict",
        tracking=True,
    )
    staff_ids = fields.One2many(
        comodel_name="sports.team.staff",
        inverse_name="team_id",
        tracking=True,
    )
    head_coach_id = fields.Many2one(
        comodel_name="res.partner",
        compute="_compute_head_coach",
        store=True,
    )
    head_coach_name = fields.Char(
        related="head_coach_id.name",
        string="Head Coach Name",
    )
    head_therapist_id = fields.Many2one(
        comodel_name="res.partner",
        compute="_compute_head_therapist",
        store=True,
        string="Head Therapist",
    )
    head_therapist_name = fields.Char(
        related="head_therapist_id.name",
        string="Head Therapist Name",
    )
    website = fields.Char()
    allowed_user_ids = fields.Many2many(
        comodel_name="res.users",
        compute="_compute_allowed_user_ids",
        inverse="_inverse_allowed_user_ids",
    )

    def write(self, vals):
        previous_patient_ids = self.sudo().patient_ids
        res = super().write(vals)
        if "staff_ids" in vals or "patient_ids" in vals:
            (self.sudo().patient_ids | previous_patient_ids).recompute_followers()
        return res

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        for index, rec in enumerate(res):
            if "staff_ids" in vals_list[index]:
                rec.sudo().patient_ids.recompute_followers()
        return res

    def unlink(self):
        to_recompute = self.patient_ids
        res = super().unlink()
        to_recompute.recompute_followers()
        return res

    @api.depends("patient_ids.is_injured")
    def _compute_player_counts(self):
        for rec in self:
            rec.player_count = len(rec.patient_ids)
            rec.injured_count = len(rec.patient_ids.filtered(lambda p: p.is_injured))
            rec.healthy_count = rec.player_count - rec.injured_count

    @api.depends("staff_ids.role")
    def _compute_head_coach(self):
        for rec in self:
            staff = rec.staff_ids.filtered(lambda r: r.role == "head_coach")
            rec.head_coach_id = staff.partner_id if staff else False

    @api.depends("staff_ids.role")
    def _compute_head_therapist(self):
        for rec in self:
            staff = rec.staff_ids.filtered(lambda r: r.role == "head_therapist")
            rec.head_therapist_id = staff.partner_id if staff else False

    def _compute_activity_count(self):
        for rec in self:
            rec.activity_count = self.env['mail.activity'].search_count([
                ('res_model', '=', 'sports.team'),
                ('res_id', '=', rec.id)
            ])

    def _compute_allowed_user_ids(self):
        for rec in self:
            rec.allowed_user_ids = rec.staff_ids.user_ids

    def _inverse_allowed_user_ids(self):
        for rec in self:
            removed_staff = rec.staff_ids.filtered(
                lambda staff: staff.user_ids not in rec.allowed_user_ids
            )
            added_users = rec.allowed_user_ids - rec.staff_ids.user_ids
            removed_staff.unlink()
            self.env["sports.team.staff"].create(
                [
                    {
                        "team_id": rec.id,
                        "partner_id": user.partner_id.id,
                        "role": "other",
                    }
                    for user in added_users
                ]
            )

    def remove_access(self, user):
        self.staff_ids.filtered(lambda staff: user in staff.user_ids).unlink()


class TeamStaff(models.Model):
    _name = "sports.team.staff"
    _description = "Sports Team Staff"

    sequence = fields.Integer()
    team_id = fields.Many2one(
        comodel_name="sports.team",
        string="Team",
        required=True,
        ondelete="cascade",
    )
    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Staff Member",
        required=True,
        domain=[("is_company", "=", False)],
        ondelete="cascade",
    )
    active = fields.Boolean(related="partner_id.active")
    role = fields.Selection(
        selection=[
            ("head_coach", "Head Coach"),
            ("head_therapist", "Head Therapist"),
            ("coach", "Coach"),
            ("therapist", "Therapist"),
            ("doctor", "Doctor"),
            ("other", "Other"),
        ],
        required=True,
    )
    mobile = fields.Char(related="partner_id.mobile", readonly=False)
    name = fields.Char(related="partner_id.name", readonly=False)
    parent_id = fields.Many2one(
        related="partner_id.parent_id",
        readonly=False,
        string="Organization",
        domain=[("is_company", "=", True)],
    )
    email = fields.Char(related="partner_id.email", readonly=False)
    user_ids = fields.One2many(related="partner_id.user_ids", readonly=True)
    has_portal_access = fields.Boolean(
        compute="_compute_has_portal_access", compute_sudo=True
    )
    silent_notifications = fields.Boolean(
        string="No Notifications",
        help="When checked, this staff member is granted access but is not "
             "added as a follower of the team's patients/injuries — they "
             "won't receive automatic notifications.",
    )
    is_auto_created = fields.Boolean(
        string="Auto-Created",
        default=False,
        help="True when this staff record was created automatically by an "
             "event-coverage assignment. Auto-created records are removed "
             "when their referencing events end or are cancelled.",
    )
    temporary_event_ids = fields.Many2many(
        comodel_name="sports.event",
        relation="sports_team_staff_event_rel",
        column1="staff_id",
        column2="event_id",
        string="Granting Events",
        help="Events that justify this temporary access. When the last "
             "event is removed and the record is auto-created, the record "
             "is unlinked.",
    )

    _sql_constraints = [
        (
            "team_staff_unique",
            "unique(team_id, partner_id)",
            "Each partner can only be related to a given team once.",
        )
    ]

    @api.constrains("role")
    def _constrain_role(self):
        teams = self.mapped("team_id")
        for team in teams:
            if len(team.staff_ids.filtered(lambda r: r.role == "head_coach")) > 1:
                raise ValidationError(_("A team can have only one head coach."))
            if len(team.staff_ids.filtered(lambda r: r.role == "head_therapist")) > 1:
                raise ValidationError(_("A team can have only one head therapist."))

    @api.onchange("mobile")
    def _onchange_mobile_validation(self):
        import logging
        _logger = logging.getLogger(__name__)
        
        _logger.info(f"Mobile validation triggered. mobile={self.mobile}, partner_id={self.partner_id}")
        
        # Check for phone formatting dependencies
        try:
            import phonenumbers
            _logger.info(f"phonenumbers library available: {phonenumbers.__version__}")
            
            # Test phonenumbers library directly
            try:
                test_number = phonenumbers.parse(self.mobile, "CA")
                _logger.info(f"phonenumbers.parse result: {test_number}")
                formatted_direct = phonenumbers.format_number(test_number, phonenumbers.PhoneNumberFormat.INTERNATIONAL)
                _logger.info(f"Direct phonenumbers formatting result: {formatted_direct}")
            except Exception as e:
                _logger.error(f"Direct phonenumbers test failed: {e}")
                
        except ImportError as e:
            _logger.error(f"phonenumbers library not available: {e}")
            return
        
        # Check if Odoo's phone formatting method exists and is callable
        if not hasattr(self.partner_id, '_phone_format'):
            _logger.error("Partner does not have _phone_format method")
            return
        
        _logger.info(f"_phone_format method available: {callable(self.partner_id._phone_format)}")
        
        if self.mobile and self.partner_id:
            try:
                _logger.info(f"Attempting to format mobile: {self.mobile}")
                country_code = self.partner_id.country_id.code if self.partner_id.country_id else None
                _logger.info(f"Partner country code: {country_code}")
                
                # Since Odoo's _phone_format is broken, use phonenumbers library directly
                if country_code:
                    try:
                        import phonenumbers
                        parsed_number = phonenumbers.parse(self.mobile, country_code)
                        if phonenumbers.is_valid_number(parsed_number):
                            formatted_mobile = phonenumbers.format_number(
                                parsed_number, phonenumbers.PhoneNumberFormat.INTERNATIONAL
                            )
                            _logger.info(f"Direct phonenumbers formatting successful: {formatted_mobile}")
                            self.mobile = formatted_mobile
                        else:
                            _logger.warning(f"Invalid phone number: {self.mobile}")
                    except Exception as e:
                        _logger.error(f"Direct phonenumbers formatting failed: {e}")
                else:
                    _logger.warning(f"No country code available for formatting")
                    
            except Exception as e:
                # If formatting fails, keep the original value
                _logger.error(f"Mobile formatting failed: {e}")
        else:
            _logger.info(f"Skipping validation - mobile: {bool(self.mobile)}, partner_id: {bool(self.partner_id)}")

    @api.depends("user_ids", "user_ids.groups_id")
    def _compute_has_portal_access(self):
        for rec in self:
            # Check if the partner has any active users with portal or internal access
            # Use direct group membership check instead of has_group() to avoid security violations
            portal_group = self.env.ref('base.group_portal')
            user_group = self.env.ref('base.group_user')
            rec.has_portal_access = (
                bool(rec.user_ids.filtered(lambda r: portal_group in r.groups_id))
                or bool(rec.user_ids.filtered(lambda r: user_group in r.groups_id))
            )

    def action_revoke_portal_access(self):
        """Public method to revoke portal access with proper permission checks."""
        # Check permissions - only admins and system users can revoke portal access
        if not (self.env.user.has_group('bemade_sports_clinic.group_sports_clinic_admin') or 
                self.env.user.has_group('base.group_system')):
            raise AccessError(_("You don't have permission to revoke portal access"))
        
        # Call the private implementation
        return self._action_revoke_portal_access()
    
    def _action_revoke_portal_access(self):
        """Private method containing the actual sudo operations for revoking portal access."""
        group_public = self.env.ref("base.group_public")
        
        # Deactivate the user and set to public user type (standard Odoo approach)
        if self.user_ids:
            self.user_ids.sudo().write(
                {
                    "groups_id": [(6, 0, [group_public.id])],  # Set to public user only
                    "active": False,
                }
            )
        
        # If there's an active signup invitation, cancel it
        # This uses the portal.wizard from Odoo core to handle all the details
        if self.partner_id and self.has_portal_access:
            self.env['res.partner'].sudo().invalidate_model(['signup_valid'])
            users = self.env['res.users'].sudo().search([('partner_id', '=', self.partner_id.id)])
            users.write({'active': False})

    def action_grant_portal_access(self):
        wiz = self.env["portal.wizard"].create(
            {"partner_ids": [(4, self.partner_id.id)]}
        )
        return wiz._action_open_modal()

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        
        # Update all portal group memberships for new records
        res._update_all_portal_groups()
        
        # Update group membership based on staff roles
        affected_users = res.mapped('user_ids')
        if affected_users:
            for user in affected_users.sudo():
                res._update_all_portal_groups(user)
        
        # Handle follower recomputation
        res.team_id.mapped("patient_ids").recompute_followers()
        return res

    def unlink(self):
        # Store affected partners and users before deletion
        affected_partners = self.mapped('partner_id')
        affected_users = self.mapped('user_ids')

        # Standard processing for follower recomputation
        patients = self.team_id.mapped("patient_ids")
        res = super().unlink()
        patients.recompute_followers()

        # Drop ex-staff users from any treatment_professional_ids on the
        # affected patients' injuries when they no longer have staff
        # access via any of the patient's other teams. Without this a
        # therapist removed from a team stays assigned to the team's
        # injuries (and as a follower) until manually scrubbed.
        # Same logic for mail.activity records pointing at those
        # injuries — the activity rule won't grant access to the
        # ex-staff user anymore, so leaving the activity assigned to
        # them produces a 403 in the portal next time they open
        # /my/activities. Reassign to a current team therapist or drop.
        if patients:
            patients.injury_ids.sudo()._cleanup_stale_treatment_professionals()
            patients.injury_ids.sudo()._cleanup_stale_mail_activities()

        # After deletion, update group memberships for all affected users
        # Use a new empty recordset to avoid using the deleted recordset
        empty_staff = self.env['sports.team.staff']
        if affected_users:
            for user in affected_users.sudo():
                # Use the comprehensive group update method for each affected user
                empty_staff._update_all_portal_groups(user)

        return res

    def _has_therapist_role(self):
        """Check if the staff member has a therapist role.
        
        Returns:
            bool: True if the staff member has a therapist role, False otherwise.
        """
        return self.role in {'head_therapist', 'therapist'}
    
    def _has_coach_role(self):
        """Check if the staff member has a coach role.
        
        Returns:
            bool: True if the staff member has a coach role, False otherwise.
        """
        return self.role in {'head_coach', 'coach'}
    
    def _get_treatment_professional_group(self):
        """Get the treatment professional security group.
        
        Returns:
            record: The treatment professional security group record.
        """
        return self.env.ref('bemade_sports_clinic.group_sports_clinic_treatment_professional')
    
    def _get_portal_coach_group(self):
        """Get the portal team coach security group.
        
        Returns:
            record: The portal team coach security group record.
        """
        return self.env.ref('bemade_sports_clinic.group_portal_team_coach')
    
    def _update_user_group_membership(self, user, should_have_access, treatment_prof_group):
        """Update group membership for a single user.
        
        Args:
            user (res.users): The user to update
            should_have_access (bool): Whether the user should have treatment professional access
            treatment_prof_group (res.groups): The treatment professional group
        """
        # Use direct group membership check instead of has_group() to avoid security violations
        has_access = treatment_prof_group in user.groups_id
        
        if should_have_access and not has_access:
            user.sudo().write({'groups_id': [(4, treatment_prof_group.id)]})
        elif not should_have_access and has_access:
            user.sudo().write({'groups_id': [(3, treatment_prof_group.id)]})
    
    def _get_staff_with_therapist_roles(self, partner_id):
        """Get all staff records with therapist roles for a partner.
        
        Args:
            partner_id (int): ID of the partner to check
            
        Returns:
            recordset: Staff records with therapist roles
        """
        return self.env['sports.team.staff'].sudo().search([
            ('partner_id', '=', partner_id),
            ('role', 'in', ['head_therapist', 'therapist', 'doctor'])
        ])
    
    def _get_staff_with_coach_roles(self, partner_id):
        """Get all staff records with coach roles for a partner.
        
        Args:
            partner_id (int): ID of the partner to check
            
        Returns:
            recordset: Staff records with coach roles
        """
        return self.env['sports.team.staff'].sudo().search([
            ('partner_id', '=', partner_id),
            ('role', 'in', ['head_coach', 'coach'])
        ])
    
    def update_all_treatment_professional_groups(self):
        """Manual method to update treatment professional group assignments for all staff.
        
        This can be called to refresh group assignments after role changes or system updates.
        Useful for fixing cases where staff members were added but not assigned to correct groups.
        
        Updated to use comprehensive group assignment that handles both therapist and coach roles.
        """
        all_staff = self.env['sports.team.staff'].search([])
        all_staff._update_all_portal_groups()
        return True
    
    def update_all_portal_groups(self):
        """Manual method to update all portal group assignments for all staff.
        
        This can be called to refresh group assignments after role changes or system updates.
        Useful for fixing cases where staff members were added but not assigned to correct groups.
        """
        all_staff = self.env['sports.team.staff'].search([])
        all_staff._update_all_portal_groups()
        return True
    
    def _update_all_portal_groups(self, specific_user=None):
        """Update all portal group assignments based on staff roles.
        
        This method ensures that users have the appropriate portal group memberships
        based on their roles. It handles both therapist and coach roles.
        
        Args:
            specific_user (res.users, optional): If provided, only update this specific user.
                                                Otherwise, update all users for the staff records.
        """
        # Skip if in module installation context to avoid demo data conflicts
        if self.env.context.get('module'):
            return
            
        treatment_prof_group = self._get_treatment_professional_group()
        portal_treatment_prof_group = self.env.ref('bemade_sports_clinic.group_portal_treatment_professional')
        portal_coach_group = self._get_portal_coach_group()
        portal_group = self.env.ref('base.group_portal')
        user_group = self.env.ref('base.group_user')
        
        if specific_user:
            # Process only the specific user
            has_therapist_role = bool(self._get_staff_with_therapist_roles(specific_user.partner_id.id))
            has_coach_role = bool(self._get_staff_with_coach_roles(specific_user.partner_id.id))

            # Log basic diagnostic info without relying on xml_id (not a real field)
            _logger.debug(
                "[SportsTeam] _update_all_portal_groups specific_user=%s partner_id=%s has_therapist_role=%s has_coach_role=%s group_ids=%s",
                specific_user.id,
                specific_user.partner_id.id,
                has_therapist_role,
                has_coach_role,
                specific_user.groups_id.ids,
            )
            
            # Handle internal users
            if user_group in specific_user.groups_id:
                # Internal users get treatment professional group for therapist roles
                if has_therapist_role and treatment_prof_group not in specific_user.groups_id:
                    specific_user.sudo().write({'groups_id': [(4, treatment_prof_group.id)]})
                    _logger.debug("[SportsTeam] Added internal treatment group to user %s", specific_user.id)
                elif not has_therapist_role and treatment_prof_group in specific_user.groups_id:
                    specific_user.sudo().write({'groups_id': [(3, treatment_prof_group.id)]})
                    _logger.debug("[SportsTeam] Removed internal treatment group from user %s", specific_user.id)
            # Handle portal users
            elif portal_group in specific_user.groups_id:
                # Portal users get appropriate portal groups
                if has_therapist_role and portal_treatment_prof_group not in specific_user.groups_id:
                    specific_user.sudo().write({'groups_id': [(4, portal_treatment_prof_group.id)]})
                    _logger.debug("[SportsTeam] Added portal treatment group to user %s", specific_user.id)
                elif not has_therapist_role and portal_treatment_prof_group in specific_user.groups_id:
                    specific_user.sudo().write({'groups_id': [(3, portal_treatment_prof_group.id)]})
                    _logger.debug("[SportsTeam] Removed portal treatment group from user %s", specific_user.id)

                if has_coach_role and portal_coach_group not in specific_user.groups_id:
                    specific_user.sudo().write({'groups_id': [(4, portal_coach_group.id)]})
                    _logger.debug("[SportsTeam] Added portal coach group to user %s", specific_user.id)
                elif not has_coach_role and portal_coach_group in specific_user.groups_id:
                    specific_user.sudo().write({'groups_id': [(3, portal_coach_group.id)]})
                    _logger.debug("[SportsTeam] Removed portal coach group from user %s", specific_user.id)
            return
        
        # Process staff members with users if no specific user provided
        for staff in self.filtered('user_ids'):
            has_therapist_role = bool(self._get_staff_with_therapist_roles(staff.partner_id.id))
            has_coach_role = bool(self._get_staff_with_coach_roles(staff.partner_id.id))
            
            for user in staff.user_ids:
                # Handle internal users
                if user_group in user.groups_id:
                    # Internal users get treatment professional group for therapist roles
                    if has_therapist_role and treatment_prof_group not in user.groups_id:
                        user.sudo().write({'groups_id': [(4, treatment_prof_group.id)]})
                    elif not has_therapist_role and treatment_prof_group in user.groups_id:
                        user.sudo().write({'groups_id': [(3, treatment_prof_group.id)]})
                # Handle portal users
                elif portal_group in user.groups_id:
                    # Portal users get appropriate portal groups
                    if has_therapist_role and portal_treatment_prof_group not in user.groups_id:
                        user.sudo().write({'groups_id': [(4, portal_treatment_prof_group.id)]})
                    elif not has_therapist_role and portal_treatment_prof_group in user.groups_id:
                        user.sudo().write({'groups_id': [(3, portal_treatment_prof_group.id)]})
                        
                    if has_coach_role and portal_coach_group not in user.groups_id:
                        user.sudo().write({'groups_id': [(4, portal_coach_group.id)]})
                    elif not has_coach_role and portal_coach_group in user.groups_id:
                        user.sudo().write({'groups_id': [(3, portal_coach_group.id)]})
    
    def _update_treatment_professional_group(self, specific_user=None):
        """Update treatment professional status based on staff role.
        
        This method ensures that users with therapist roles have the appropriate
        group memberships. It handles both internal and portal users appropriately.
        
        For internal users, this manages group membership directly.
        For portal users, it manages the portal treatment professional group.
        
        Args:
            specific_user (res.users, optional): If provided, only update this specific user.
                                                Otherwise, update all users for the staff records.
        """
        # Skip if in module installation context to avoid demo data conflicts
        if self.env.context.get('module'):
            return
            
        treatment_prof_group = self._get_treatment_professional_group()
        portal_treatment_prof_group = self.env.ref('bemade_sports_clinic.group_portal_treatment_professional')
        
        if specific_user:
            # Process only the specific user
            staff = self.filtered(lambda s: specific_user in s.user_ids)
            if not staff:
                # Check if the user has any therapist roles through their partner
                has_therapist_role = bool(self._get_staff_with_therapist_roles(specific_user.partner_id.id))
                users_to_process = specific_user
            else:
                # Check if this partner has any staff records with therapist roles
                has_therapist_role = bool(self._get_staff_with_therapist_roles(specific_user.partner_id.id))
                users_to_process = specific_user
            
            # Apply the appropriate group membership
            # Use direct group membership check instead of has_group() to avoid security violations
            portal_group = self.env.ref('base.group_portal')
            if portal_group not in users_to_process.groups_id:
                # Internal user
                if has_therapist_role and treatment_prof_group not in users_to_process.groups_id:
                    users_to_process.sudo().write({'groups_id': [(4, treatment_prof_group.id)]})
                elif not has_therapist_role and treatment_prof_group in users_to_process.groups_id:
                    users_to_process.sudo().write({'groups_id': [(3, treatment_prof_group.id)]})
            else:
                # Portal user
                if has_therapist_role and portal_treatment_prof_group not in users_to_process.groups_id:
                    users_to_process.sudo().write({'groups_id': [(4, portal_treatment_prof_group.id)]})
                elif not has_therapist_role and portal_treatment_prof_group in users_to_process.groups_id:
                    users_to_process.sudo().write({'groups_id': [(3, portal_treatment_prof_group.id)]})
            return
        
        # Process staff members with users if no specific user provided
        for staff in self.filtered('user_ids'):
            # Check if this partner has any staff records with therapist roles
            has_therapist_role = bool(self._get_staff_with_therapist_roles(staff.partner_id.id))
            
            # Process each user linked to this partner
            portal_group = self.env.ref('base.group_portal')
            user_group = self.env.ref('base.group_user')
            for user in staff.user_ids:
                # Handle internal users
                if user_group in user.groups_id:
                    self._update_user_group_membership(user, has_therapist_role, treatment_prof_group)
                # Handle portal users
                elif portal_group in user.groups_id:
                    if has_therapist_role and portal_treatment_prof_group not in user.groups_id:
                        user.sudo().write({'groups_id': [(4, portal_treatment_prof_group.id)]})
                    elif not has_therapist_role and portal_treatment_prof_group in user.groups_id:
                        user.sudo().write({'groups_id': [(3, portal_treatment_prof_group.id)]})
    
    def write(self, values):
        previous_patients = self.team_id.patient_ids if 'team_id' in values else self.env['sports.patient']
        result = super().write(values)

        if 'role' in values or 'team_id' in values:
            self._update_all_portal_groups()

        if 'team_id' in values or 'silent_notifications' in values or 'role' in values:
            affected_patients = self.team_id.patient_ids | previous_patients
            affected_patients.recompute_followers()
            # If team_id moved a staff member to a different team, the
            # patients on the *previous* team may have stale TP injury
            # assignments to clean up. (silent_notifications and role
            # changes don't affect access to the patient itself.)
            if 'team_id' in values and previous_patients:
                previous_patients.injury_ids.sudo()._cleanup_stale_treatment_professionals()
                previous_patients.injury_ids.sudo()._cleanup_stale_mail_activities()

        return result
