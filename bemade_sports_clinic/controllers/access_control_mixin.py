# -*- coding: utf-8 -*-
#
#    Bemade Inc.
#
#    Copyright (C) October 2023 Bemade Inc. (<https://www.bemade.org>).
#    Author: Marc Durepos (Contact : marc@bemade.org)
#
#    This program is under the terms of the Odoo Proprietary License v1.0 (OPL-1)
#    It is forbidden to publish, distribute, sublicense, or sell copies of the Software
#    or modified copies of the Software.
#
#    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
#    IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
#    DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
#    ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
#    DEALINGS IN THE SOFTWARE.
#

from odoo import http, _
from odoo.exceptions import UserError, AccessError, MissingError
from odoo.http import request


class AccessControlMixin:
    """
    Mixin class providing common access control methods for portal controllers.
    
    This centralizes access control logic to avoid duplication across multiple controllers
    and ensures consistent security checks throughout the portal interface.
    """
    
    def _check_team_access(self, team_id, check_staff=False):
        """
        Verify the current user has access to this team.
        
        :param int team_id: ID of the team to check access for
        :param bool check_staff: If True, only allow team staff members
        :return: The team record if access is granted
        :raises: MissingError if team not found
        :raises: AccessError if user doesn't have permission
        """
        team = request.env['sports.team'].browse(int(team_id))
        if not team.exists():
            raise MissingError(_("Team not found"))
            
        user = request.env.user
        
        # Check if user is a staff member of this team
        is_team_staff = team.staff_ids.filtered(
            lambda s: user.partner_id in s.user_ids.partner_id
        )
        
        # Check if user is a treatment professional with access
        is_treatment_professional = request.env.user.has_group(
            'bemade_sports_clinic.group_portal_treatment_professional'
        )
        
        if check_staff and not is_team_staff:
            # Only team staff can perform certain actions
            raise AccessError(_("Only team staff members can perform this action."))
            
        if not (is_team_staff or is_treatment_professional):
            raise AccessError(_("You don't have permission to access this team."))
            
        return team
    
    def _check_team_staff_access(self, team):
        """
        Check if the current user is a staff member of the team.
        
        :param team: Team record to check staff access for
        :return: Staff records if user is team staff, empty recordset otherwise
        """
        user = request.env.user
        return team.staff_ids.filtered(
            lambda s: user.partner_id in s.user_ids.partner_id
        )
    
    def _check_treatment_professional_access(self):
        """
        Check if the current user is a treatment professional (portal or internal)
        or a system admin.

        :return: True if user is a treatment professional or system admin
        """
        user = request.env.user
        return (user.has_group('bemade_sports_clinic.group_portal_treatment_professional') or
                user.has_group('bemade_sports_clinic.group_sports_clinic_treatment_professional') or
                user.has_group('base.group_system'))
    
    def _check_access_to_patient(self, patient_id):
        """
        Verify the user has access to this patient.

        :param int patient_id: ID of the patient to check access for
        :return: The patient record if access is granted
        :raises: UserError if user doesn't have permission or patient not found
        """
        user = request.env.user
        patient = request.env['sports.patient'].browse(int(patient_id))

        if not patient.exists():
            raise UserError(_('Patient not found.'))

        # Record access is team-gated for EVERYONE, including treatment
        # professionals: a TP may find an unteamed patient in portal search
        # (see TeamStaffPortal._prepare_players_domain, task 640) to add them to
        # a team, but full patient-record access requires being staff on one of
        # the patient's teams. System admins always pass.
        if user.has_group('base.group_system'):
            return patient

        user_teams = user.partner_id.team_staff_rel_ids.mapped('team_id')
        patient_teams = patient.team_ids
        if not (user_teams & patient_teams):
            raise UserError(_('You do not have access to this patient.'))

        return patient

    def _check_access_to_injury(self, injury_id):
        """
        Verify the user has access to this injury.

        :param int injury_id: ID of the injury to check access for
        :return: The injury record if access is granted
        :raises: UserError if user doesn't have permission or injury not found
        """
        user = request.env.user
        injury = request.env['sports.patient.injury'].browse(int(injury_id))

        if not injury.exists():
            raise UserError(_('Injury not found.'))

        # Team-gated for everyone (see _check_access_to_patient, task 640).
        # System admins always pass.
        if user.has_group('base.group_system'):
            return injury

        user_teams = user.partner_id.team_staff_rel_ids.mapped('team_id')
        patient_teams = injury.patient_id.team_ids
        if not (user_teams & patient_teams):
            raise UserError(_('You do not have access to this injury.'))

        return injury

    def _check_access_to_event(self, event_id):
        """Verify the user has access to this event.

        Mirror the access semantics used by the event portal:
        - treatment professionals can access event records
        - coaches must be staff on at least one of the event teams
        - system users always allowed
        """
        user = request.env.user
        event = request.env['sports.event'].browse(int(event_id))

        if not event.exists():
            raise UserError(_('Event not found.'))

        is_therapist = user.has_group('bemade_sports_clinic.group_portal_treatment_professional') or \
            user.has_group('bemade_sports_clinic.group_sports_clinic_treatment_professional')
        is_coach = user.has_group('bemade_sports_clinic.group_portal_team_coach')

        if user.has_group('base.group_system'):
            return event

        if is_therapist:
            return event

        if is_coach:
            user_teams = user.partner_id.team_staff_rel_ids.mapped('team_id')
            has_team_access = bool(user_teams & event.team_ids)
            if not has_team_access:
                raise UserError(_('You do not have access to this event.'))
            return event

        raise UserError(_('You do not have access to this event.'))
    
    def _check_access_to_task_model(self, model_name, record_id):
        """
        Verify the user has access to a task-related model record.
        
        :param str model_name: Name of the model ('sports.patient', 'sports.team', 'sports.patient.injury')
        :param int record_id: ID of the record to check access for
        :return: The record if access is granted
        :raises: UserError if user doesn't have permission or record not found
        """
        valid_models = ['sports.patient', 'sports.patient.injury', 'sports.team', 'sports.event']
        if model_name not in valid_models:
            raise UserError(_('Invalid model specified.'))
        
        if model_name == 'sports.patient':
            return self._check_access_to_patient(record_id)
        elif model_name == 'sports.patient.injury':
            return self._check_access_to_injury(record_id)
        elif model_name == 'sports.team':
            return self._check_team_access(record_id)
        elif model_name == 'sports.event':
            return self._check_access_to_event(record_id)
        
        # This should never be reached due to the valid_models check above
        raise UserError(_('Invalid model specified.'))
