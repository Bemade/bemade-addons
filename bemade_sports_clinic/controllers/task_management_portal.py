import logging
from odoo import http, fields, _
from odoo.exceptions import UserError, ValidationError
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager
from .access_control_mixin import AccessControlMixin
from datetime import date, timedelta

_logger = logging.getLogger(__name__)


class TaskManagementPortal(CustomerPortal, AccessControlMixin):
    """Controller for task management functionality in the portal"""
    
    # Access control methods now inherited from AccessControlMixin
    
    @http.route(['/my/activities'], type='http', auth='user', website=True)
    def view_activities(self, model=None, res_id=None, simplified=False, team_id=None, **kw):
        """Display list of activities accessible to the current user through team relationships.

        When ``simplified`` is True (used by object-specific wrappers), the
        template renders a single list view without the global dashboard tabs.
        """
        user = request.env.user
        partner = user.partner_id
        
        team_staff_rels = partner.team_staff_rel_ids
        
        team_ids = team_staff_rels.mapped('team_id.id')
        
        # Build search domain with team-based filtering
        # Record rules provide broad CRUD access, controller enforces team-based security
        
        # Build team-based access domain for security filtering
        team_access_domain = [
            '|', '|', '|',
            '&', '&',
            ('res_model', '=', 'sports.patient'),
            ('res_id', '!=', False),
            ('res_id', 'in', team_staff_rels.mapped('team_id.patient_ids.id') or [0]),
            '&', '&',
            ('res_model', '=', 'sports.patient.injury'),
            ('res_id', '!=', False),
            ('res_id', 'in', team_staff_rels.mapped('team_id.patient_ids.injury_ids.id') or [0]),
            '&', '&',
            ('res_model', '=', 'sports.team'),
            ('res_id', '!=', False),
            ('res_id', 'in', team_staff_rels.mapped('team_id.id') or [0]),
            '&', '&',
            ('res_model', '=', 'sports.event'),
            ('res_id', '!=', False),
            ('res_id', 'in', team_staff_rels.mapped('team_id.event_ids.id') or [0])
        ]
        
        # Activities are scoped strictly by the team-based access domain. We used to
        # OR-in `(user_id == self) AND res_model in [...]` so a portal user could see
        # activities personally assigned to them, but that left orphan assignee
        # activities (e.g. cron-created "Verify injury" tasks left over after a TP
        # was unstaffed from a team) visible while their related record was no
        # longer readable, causing 403s when the template browsed the related
        # injury for display. Aligning with the ir.rule keeps the listing
        # consistent with what the user can actually open.

        if model:
            domain = ['&', ('res_model', '=', model)] + team_access_domain
            if res_id:
                domain = ['&', ('res_id', '=', int(res_id))] + domain
        else:
            domain = team_access_domain
        
        # Search for activities with both assignment and team-based access control
        activities = request.env['mail.activity'].search(domain, order='date_deadline asc')
        
        # Group activities by model
        patient_activities = activities.filtered(lambda a: a.res_model == 'sports.patient')
        injury_activities = activities.filtered(lambda a: a.res_model == 'sports.patient.injury')
        team_activities = activities.filtered(lambda a: a.res_model == 'sports.team')
        event_activities = activities.filtered(lambda a: a.res_model == 'sports.event')

        # Resolve optional context records for breadcrumbs
        context_team = None
        context_patient = None
        context_injury = None
        context_event = None

        if model and res_id:
            try:
                if model == 'sports.team':
                    context_team = request.env['sports.team'].browse(int(res_id))
                elif model == 'sports.patient':
                    context_patient = request.env['sports.patient'].browse(int(res_id))
                elif model == 'sports.patient.injury':
                    context_injury = request.env['sports.patient.injury'].browse(int(res_id))
                    context_patient = context_injury.patient_id if context_injury.exists() else None
                elif model == 'sports.event':
                    context_event = request.env['sports.event'].browse(int(res_id))
            except Exception:
                # If anything goes wrong resolving context, fall back to global view
                context_team = context_patient = context_injury = context_event = None

        # Optional explicit team context (used when viewing a player's or injury's activities
        # from a team page). The wrapper routes have already validated team_id via
        # _check_team_access, so here we only need to resolve the record for breadcrumbs.
        if team_id:
            try:
                explicit_team = request.env['sports.team'].browse(int(team_id))
                if explicit_team.exists():
                    context_team = explicit_team
            except Exception:
                # If team resolution fails, keep existing context_team (if any)
                pass
        
        # Get activity types for filtering
        activity_types = request.env['mail.activity.type'].search([])
        
        # Get available users for reassignment (treatment professionals)
        # Include both portal and internal treatment professional groups so internal
        # clinicians (e.g., doctors) appear as valid assignees.
        portal_tp_group = request.env.ref('bemade_sports_clinic.group_portal_treatment_professional')
        internal_tp_group = request.env.ref('bemade_sports_clinic.group_sports_clinic_treatment_professional')
        available_users = request.env['res.users'].search([
            ('groups_id', 'in', [portal_tp_group.id, internal_tp_group.id])
        ])
        
        values = {
            'activities': activities,
            'patient_activities': patient_activities,
            'injury_activities': injury_activities,
            'team_activities': team_activities,
            'event_activities': event_activities,
            'activity_types': activity_types,
            'available_users': available_users,
            'page_name': 'activities',
            'today': date.today().strftime('%Y-%m-%d'),
            'show_assignee': bool(model),  # Show assignee column when viewing specific records
            'context_model': model,
            'context_res_id': res_id,
            'context_team': context_team,
            'context_patient': context_patient,
            'context_injury': context_injury,
            'context_event': context_event,
            'simplified': bool(simplified),
        }
        
        return request.render('bemade_sports_clinic.portal_my_activities', values)
    
    @http.route(['/my/activity/create'], type='http', auth='user', website=True)
    def create_activity_form(self, model=None, res_id=None, **kw):
        """Display form to create a new activity"""
        # Validate model and res_id
        valid_models = ['sports.patient', 'sports.patient.injury', 'sports.team', 'sports.event']
        if model not in valid_models or not res_id:
            return request.redirect('/my/activities')
            
        try:
            record = self._check_access_to_task_model(model, res_id)
        except UserError as e:
            response = request.render('http_routing.http_error', {
                'status_code': 403,
                'status_message': 'Forbidden',
                'error_message': str(e),
            })
            response.status_code = 403
            return response

        # Get activity types
        activity_types = request.env['mail.activity.type'].search([])
        # Determine default activity type robustly
        # 1) Try canonical XML-ID from mail: 'mail.mail_activity_data_todo'
        default_activity_type = request.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
        # 2) Fallback: category 'todo'
        if not default_activity_type:
            default_activity_type = request.env['mail.activity.type'].search([('category', '=', 'todo')], limit=1)
        # 3) Fallback: name contains 'todo'
        if not default_activity_type:
            default_activity_type = request.env['mail.activity.type'].search([('name', 'ilike', 'todo')], limit=1)
        
        # Get users that can be assigned to activities
        domain = []
        
        # If this is an injury record, filter by team staff
        if model == 'sports.patient.injury':
            team = record.team_id
            if team:
                domain = [('partner_id', 'in', team.staff_ids.mapped('partner_id').ids)]
                
        # Only treatment professionals can see and assign all users
        is_treatment_prof = request.env.user.has_group('bemade_sports_clinic.group_portal_treatment_professional')
        if not is_treatment_prof:
            domain.append(('id', '=', request.env.user.id))
            
        assignable_users = request.env['res.users'].search(domain)
        
        # Prepare record name for display
        record_name = record.name if hasattr(record, 'name') else record.display_name
        
        # Default return URL (when no explicit return_url query param is provided)
        team_id_param = kw.get('team_id') or request.params.get('team_id')

        if model == 'sports.patient':
            # Optional team_id can be passed for team-aware navigation, but
            # explicit return_url (if present) always wins.
            if team_id_param:
                try:
                    team_id_int = int(team_id_param)
                except Exception:
                    team_id_int = None
                if team_id_int:
                    return_url = f'/my/player?player_id={res_id}&team_id={team_id_int}'
                else:
                    return_url = f'/my/player?player_id={res_id}'
            else:
                team_id_param = None
                return_url = f'/my/player?player_id={res_id}'
        elif model == 'sports.team':
            return_url = f'/my/team?team_id={res_id}'
        elif model == 'sports.event':
            return_url = f'/my/event?event_id={res_id}'
        else:  # sports.patient.injury
            # For injury activities, default back to the player (optionally in team context)
            if team_id_param:
                try:
                    team_id_int = int(team_id_param)
                except Exception:
                    team_id_int = None
                if team_id_int:
                    return_url = f'/my/player?player_id={record.patient_id.id}&team_id={team_id_int}'
                else:
                    return_url = f'/my/player?player_id={record.patient_id.id}'
            else:
                team_id_param = None
                return_url = f'/my/player?player_id={record.patient_id.id}'
            
        from datetime import date

        raw_return_url = kw.get('return_url')
        if raw_return_url and isinstance(raw_return_url, str) and '&amp;' in raw_return_url:
            raw_return_url = raw_return_url.replace('&amp;', '&')
        if not raw_return_url or raw_return_url in ('None', 'none', 'null', 'NULL'):
            raw_return_url = None
        if raw_return_url and not str(raw_return_url).startswith('/'):
            raw_return_url = None
    
        values = {
            'activity_types': activity_types,
            'assignable_users': assignable_users,
            'record': record,
            'record_name': record_name,
            'model': model,
            'res_id': res_id,
            'default_user_id': request.env.user.id,
            'default_activity_type_id': default_activity_type.id if default_activity_type else False,
            'return_url': raw_return_url or return_url,
            'team_id': team_id_param if model in ('sports.patient', 'sports.patient.injury') else None,
            'page_name': 'create_activity',
            'today': date.today().strftime('%Y-%m-%d'),
        }
        
        return request.render('bemade_sports_clinic.portal_create_activity', values)

    @http.route(['/my/player/activities'], type='http', auth='user', website=True)
    def view_player_activities(self, player_id=None, team_id=None, **kw):
        """Object-specific wrapper: activities for a single player.

        Delegates to ``view_activities`` with ``model='sports.patient'`` and
        a simplified, single-list view.
        """
        if not player_id:
            return request.redirect('/my/players')

        try:
            patient = self._check_access_to_patient(player_id)
        except UserError as e:
            return request.render('http_routing.http_error', {
                'status_code': 403,
                'status_message': 'Forbidden',
                'error_message': str(e),
            })

        # When a team_id is provided, validate explicit team context so that
        # breadcrumbs can include the team in the trail. This mirrors
        # team_context_id usage elsewhere but is scoped locally to activities.
        validated_team_id = None
        if team_id:
            try:
                team = self._check_team_access(team_id, check_staff=True)
                if team:
                    validated_team_id = team.id
            except UserError:
                validated_team_id = None

        return self.view_activities(
            model='sports.patient',
            res_id=patient.id,
            simplified=True,
            team_id=validated_team_id,
        )

    @http.route(['/my/team/activities'], type='http', auth='user', website=True)
    def view_team_activities(self, team_id=None, **kw):
        """Object-specific wrapper: activities for a single team."""
        if not team_id:
            return request.redirect('/my/teams')

        try:
            team = self._check_team_access(team_id, check_staff=True)
        except UserError as e:
            return request.render('http_routing.http_error', {
                'status_code': 403,
                'status_message': 'Forbidden',
                'error_message': str(e),
            })

        return self.view_activities(model='sports.team', res_id=team.id, simplified=True)

    @http.route(['/my/injury/activities'], type='http', auth='user', website=True)
    def view_injury_activities(self, injury_id=None, team_id=None, **kw):
        """Object-specific wrapper: activities for a single injury."""
        if not injury_id:
            return request.redirect('/my/players')

        try:
            injury = self._check_access_to_injury(injury_id)
        except UserError as e:
            return request.render('http_routing.http_error', {
                'status_code': 403,
                'status_message': 'Forbidden',
                'error_message': str(e),
            })

        # Optional explicit team context so breadcrumbs can include
        # Teams > Team > Player > Injury > Activities for injury views
        # reached from a specific team.
        validated_team_id = None
        if team_id:
            try:
                team = self._check_team_access(team_id, check_staff=True)
                if team:
                    validated_team_id = team.id
            except UserError:
                validated_team_id = None

        return self.view_activities(
            model='sports.patient.injury',
            res_id=injury.id,
            simplified=True,
            team_id=validated_team_id,
        )

    @http.route(['/my/event/activities'], type='http', auth='user', website=True)
    def view_event_activities(self, event_id=None, **kw):
        """Object-specific wrapper: activities for a single event."""
        if not event_id:
            return request.redirect('/my/events')

        try:
            event = self._check_access_to_task_model('sports.event', event_id)
        except UserError as e:
            return request.render('http_routing.http_error', {
                'status_code': 403,
                'status_message': 'Forbidden',
                'error_message': str(e),
            })

        return self.view_activities(model='sports.event', res_id=event.id, simplified=True)
    
    @http.route(['/my/activity/save'], type='http', auth='user', website=True, methods=['POST'], csrf=False)
    def create_activity_submit(self, **post):
        """Process form submission to create a new activity"""
        model = post.get('model')
        res_id = post.get('res_id')
        
        # Validate model and res_id
        valid_models = ['sports.patient', 'sports.patient.injury', 'sports.team', 'sports.event']
        if model not in valid_models or not res_id:
            return request.redirect('/my/activities')
            
        try:
            record = self._check_access_to_task_model(model, res_id)
        except UserError as e:
            response = request.render('http_routing.http_error', {
                'status_code': 403,
                'status_message': 'Forbidden',
                'error_message': str(e),
            })
            response.status_code = 403
            return response

        # Validate required fields
        activity_type_id = post.get('activity_type_id')
        summary = post.get('summary')
        user_id = post.get('user_id')
        date_deadline = post.get('date_deadline')
        
        def _sanitize_return_url(val, default):
            if val and isinstance(val, str) and '&amp;' in val:
                val = val.replace('&amp;', '&')
            if not val or val in ('None', 'none', 'null', 'NULL'):
                return default
            if not str(val).startswith('/'):
                return default
            return val

        default_return_url = '/my/activities'
        if model == 'sports.patient':
            default_return_url = f'/my/player?player_id={int(res_id)}'
        elif model == 'sports.team':
            default_return_url = f'/my/team?team_id={int(res_id)}'
        elif model == 'sports.event':
            default_return_url = f'/my/event/{int(res_id)}'
        elif model == 'sports.patient.injury':
            try:
                default_return_url = f'/my/player?player_id={record.patient_id.id}'
            except Exception:
                default_return_url = '/my/activities'

        if not activity_type_id or not summary or not user_id or not date_deadline:
            return_url = _sanitize_return_url(post.get('return_url'), default_return_url)
            separator = '&' if '?' in return_url else '?'
            return request.redirect(f'{return_url}{separator}error=missing_fields')
            
        # Check if the assigned user is valid
        is_treatment_prof = request.env.user.has_group('bemade_sports_clinic.group_portal_treatment_professional')
        assigned_user = request.env['res.users'].browse(int(user_id))
        
        # Only treatment professionals can assign to other users
        if not is_treatment_prof and assigned_user.id != request.env.user.id:
            return_url = _sanitize_return_url(post.get('return_url'), default_return_url)
            separator = '&' if '?' in return_url else '?'
            return request.redirect(f'{return_url}{separator}error=invalid_user')
            
        # Create the activity
        # Get model ID - portal users now have ACL access to ir.model
        model_id = request.env['ir.model'].search([('model', '=', model)], limit=1).id
        if not model_id:
            return_url = _sanitize_return_url(post.get('return_url'), default_return_url)
            separator = '&' if '?' in return_url else '?'
            return request.redirect(f'{return_url}{separator}error=invalid_model')
            
        vals = {
            'activity_type_id': int(activity_type_id),
            'summary': summary,
            'note': post.get('note', ''),
            'user_id': int(user_id),
            'date_deadline': date_deadline,
            'res_model_id': model_id,
            'res_id': int(res_id),
        }
        
        # Create activity using sudo to bypass notification access issues for portal users
        # This is safe because we've already validated all inputs and access permissions above
        activity = request.env['mail.activity'].sudo().create(vals)
        
        # Redirect to the return URL or activities page, preserving optional team context
        return_url = _sanitize_return_url(post.get('return_url'), default_return_url)

        # For player or injury activities, ensure team_id is not lost when coming
        # from a team-aware context. If a team_id was posted but is missing from
        # return_url, append it.
        if model in ('sports.patient', 'sports.patient.injury'):
            team_id = post.get('team_id')
            if team_id and 'team_id=' not in return_url:
                sep_team = '&' if '?' in return_url else '?'
                return_url = f'{return_url}{sep_team}team_id={int(team_id)}'

        separator = '&' if '?' in return_url else '?'
        return request.redirect(f'{return_url}{separator}success=activity_created')
    
    @http.route(['/my/activity/update'], type='http', auth='user', website=True, methods=['POST'], csrf=False)
    def update_activity(self, **post):
        """Update an existing activity"""
        activity_id = post.get('activity_id')
        if not activity_id:
            return request.redirect('/my/activities')
            
        activity = request.env['mail.activity'].browse(int(activity_id))
        
        # Check if the activity exists
        if not activity.exists():
            return request.redirect('/my/activities')
        
        # Check access using team-based access control
        user = request.env.user
        partner = user.partner_id
        has_access = False
        
        # Allow access if user is assigned to the activity
        if activity.user_id == user:
            has_access = True
        else:
            # Check if user has access through team relationships
            if activity.res_model == 'sports.patient':
                patient = request.env['sports.patient'].browse(activity.res_id)
                if patient.exists():
                    user_teams = partner.team_staff_rel_ids.mapped('team_id')
                    patient_teams = patient.team_ids
                    has_access = bool(user_teams & patient_teams)
            elif activity.res_model == 'sports.patient.injury':
                injury = request.env['sports.patient.injury'].browse(activity.res_id)
                if injury.exists():
                    user_teams = partner.team_staff_rel_ids.mapped('team_id')
                    patient_teams = injury.patient_id.team_ids
                    has_access = bool(user_teams & patient_teams)
            elif activity.res_model == 'sports.team':
                team = request.env['sports.team'].browse(activity.res_id)
                if team.exists():
                    user_teams = partner.team_staff_rel_ids.mapped('team_id')
                    has_access = bool(user_teams & team)
            elif activity.res_model == 'sports.event':
                event = request.env['sports.event'].browse(activity.res_id)
                if event.exists():
                    user_teams = partner.team_staff_rel_ids.mapped('team_id')
                    has_access = bool(user_teams & event.team_ids)
        
        if not has_access:
            return request.redirect('/my/activities')
        
        # Update activity fields
        update_vals = {}
        if 'summary' in post:
            update_vals['summary'] = post['summary']
        if 'note' in post:
            update_vals['note'] = post['note']
        if 'date_deadline' in post:
            update_vals['date_deadline'] = post['date_deadline']
        
        if update_vals:
            activity.write(update_vals)
        
        # Redirect to activities page or return URL
        return_url = post.get('return_url', '/my/activities')
        separator = '&' if '?' in return_url else '?'
        return request.redirect(f'{return_url}{separator}success=activity_updated')
    
    @http.route(['/my/activity/complete'], type='http', auth='user', website=True, methods=['POST'], csrf=False)
    def complete_activity(self, **post):
        """Mark an activity as done"""
        activity_id = post.get('activity_id')
        if not activity_id:
            return request.redirect('/my/activities')
            
        activity = request.env['mail.activity'].browse(int(activity_id))
        
        # Check if the activity exists and user has access (record rules will handle this)
        if not activity.exists():
            return request.redirect('/my/activities')
            
        # Add feedback if provided
        feedback = post.get('feedback', '')
        
        # Mark the activity as done
        activity.action_feedback(feedback=feedback)
        return request.redirect('/my/activities')

    @http.route(['/my/activity/cancel'], type='http', auth='user', website=True, methods=['POST'], csrf=False)
    def cancel_activity(self, **post):
        """Cancel (delete) an activity."""
        activity_id = post.get('activity_id')
        if not activity_id:
            return request.redirect('/my/activities')

        activity = request.env['mail.activity'].browse(int(activity_id))
        if not activity.exists():
            return request.redirect('/my/activities')

        user = request.env.user
        partner = user.partner_id

        # Allow access if user is assigned to the activity
        if activity.user_id == user:
            has_access = True
        else:
            has_access = False
            if activity.res_model == 'sports.patient':
                patient = request.env['sports.patient'].browse(activity.res_id)
                if patient.exists():
                    user_teams = partner.team_staff_rel_ids.mapped('team_id')
                    has_access = bool(user_teams & patient.team_ids)
            elif activity.res_model == 'sports.patient.injury':
                injury = request.env['sports.patient.injury'].browse(activity.res_id)
                if injury.exists():
                    user_teams = partner.team_staff_rel_ids.mapped('team_id')
                    has_access = bool(user_teams & injury.patient_id.team_ids)
            elif activity.res_model == 'sports.team':
                team = request.env['sports.team'].browse(activity.res_id)
                if team.exists():
                    user_teams = partner.team_staff_rel_ids.mapped('team_id')
                    has_access = bool(user_teams & team)
            elif activity.res_model == 'sports.event':
                event = request.env['sports.event'].browse(activity.res_id)
                if event.exists():
                    user_teams = partner.team_staff_rel_ids.mapped('team_id')
                    has_access = bool(user_teams & event.team_ids)

        if not has_access:
            return request.redirect('/my/activities')

        activity.unlink()
        return request.redirect('/my/activities')
    
    @http.route(['/my/activity/reschedule'], type='http', auth='user', website=True, methods=['POST'])
    def reschedule_activity(self, **post):
        """Reschedule an activity to a new date"""
        activity_id = post.get('activity_id')
        if not activity_id:
            return request.redirect('/my/activities')
            
        activity = request.env['mail.activity'].browse(int(activity_id))
        
        # Check if the activity exists and belongs to the current user
        if not activity.exists() or activity.user_id != request.env.user:
            return request.redirect('/my/activities')
            
        # Get new deadline
        new_deadline = post.get('new_deadline')
        if not new_deadline:
            return request.redirect('/my/activities')
            
        # Update the deadline
        activity.write({'date_deadline': new_deadline})
        
        # Redirect to activities page
        return request.redirect('/my/activities')
    
    @http.route(['/my/activity/reassign'], type='http', auth='user', website=True, methods=['POST'], csrf=False)
    def reassign_activity(self, **post):
        """Reassign an activity to a different user"""
        activity_id = post.get('activity_id')
        new_user_id = post.get('new_user_id')
        
        if not activity_id or not new_user_id:
            return request.redirect('/my/activities')
            
        activity = request.env['mail.activity'].browse(int(activity_id))
        new_user = request.env['res.users'].browse(int(new_user_id))
        
        # Check if the activity exists and user has access to it
        if not activity.exists() or not new_user.exists():
            return request.redirect('/my/activities')
            
        # Verify new user is a treatment professional (portal or internal).
        # Do not use has_group() on arbitrary users; instead, check group
        # membership via groups_id to avoid security restrictions.
        portal_tp_group = request.env.ref('bemade_sports_clinic.group_portal_treatment_professional')
        internal_tp_group = request.env.ref('bemade_sports_clinic.group_sports_clinic_treatment_professional')
        if not (portal_tp_group in new_user.groups_id or internal_tp_group in new_user.groups_id):
            return request.redirect('/my/activities')
            
        # Check access permissions (user must have team access to the record)
        user = request.env.user
        partner = user.partner_id
        has_access = False
        
        if activity.res_model == 'sports.patient':
            patient = request.env['sports.patient'].browse(activity.res_id)
            if patient.exists():
                user_teams = partner.team_staff_rel_ids.mapped('team_id')
                patient_teams = patient.team_ids
                has_access = bool(user_teams & patient_teams)
        elif activity.res_model == 'sports.patient.injury':
            injury = request.env['sports.patient.injury'].browse(activity.res_id)
            if injury.exists():
                user_teams = partner.team_staff_rel_ids.mapped('team_id')
                patient_teams = injury.patient_id.team_ids
                has_access = bool(user_teams & patient_teams)
        elif activity.res_model == 'sports.team':
            team = request.env['sports.team'].browse(activity.res_id)
            if team.exists():
                user_teams = partner.team_staff_rel_ids.mapped('team_id')
                has_access = team in user_teams

        elif activity.res_model == 'sports.event':
            event = request.env['sports.event'].browse(activity.res_id)
            if event.exists():
                user_teams = partner.team_staff_rel_ids.mapped('team_id')
                has_access = bool(user_teams & event.team_ids)
                
        if not has_access:
            return request.redirect('/my/activities')
            
        # Reassign the activity
        # Perform the actual reassignment with sudo to bypass mail.activity ACL
        # constraints for portal coaches. This is safe because we've already
        # validated:
        # - the activity exists
        # - the new user is a (portal or internal) treatment professional
        # - the current user has team-based access to the related record.
        activity.sudo().write({'user_id': new_user.id})
        
        # Determine return URL based on context
        return_url = post.get('return_url', '/my/activities')
        separator = '&' if '?' in return_url else '?'
        return request.redirect(f'{return_url}{separator}success=activity_reassigned')

    @http.route(['/my/activity/<int:activity_id>/edit'], type='http', auth='user', website=True)
    def edit_activity_form(self, activity_id, **kw):
        """Display form to edit an existing activity"""
        activity = request.env['mail.activity'].browse(activity_id)
        
        # Check if the activity exists and user has access to it
        if not activity.exists():
            raise request.not_found()
            
        # Check access permissions using the same logic as view_activity_detail
        user = request.env.user
        partner = user.partner_id
        
        # Allow access if user is assigned to the activity
        if activity.user_id == user:
            has_access = True
        else:
            # Check if user has access through team relationships
            has_access = False
            if activity.res_model == 'sports.patient':
                patient = request.env['sports.patient'].browse(activity.res_id)
                if patient.exists():
                    # Check if user is staff on any of the patient's teams
                    user_teams = partner.team_staff_rel_ids.mapped('team_id')
                    patient_teams = patient.team_ids
                    has_access = bool(user_teams & patient_teams)
            elif activity.res_model == 'sports.patient.injury':
                injury = request.env['sports.patient.injury'].browse(activity.res_id)
                if injury.exists():
                    # Check if user is staff on any of the injury patient's teams
                    user_teams = partner.team_staff_rel_ids.mapped('team_id')
                    patient_teams = injury.patient_id.team_ids
                    has_access = bool(user_teams & patient_teams)
            elif activity.res_model == 'sports.team':
                team = request.env['sports.team'].browse(activity.res_id)
                if team.exists():
                    user_teams = partner.team_staff_rel_ids.mapped('team_id')
                    has_access = bool(user_teams & team)
            elif activity.res_model == 'sports.event':
                event = request.env['sports.event'].browse(activity.res_id)
                if event.exists():
                    user_teams = partner.team_staff_rel_ids.mapped('team_id')
                    has_access = bool(user_teams & event.team_ids)
        if not has_access:
            raise request.not_found()
        
        # Get activity types for the form
        activity_types = request.env['mail.activity.type'].search([
            ('res_model', 'in', ['sports.patient', 'sports.patient.injury', 'sports.team', 'sports.event', False])
        ])
        
        # Get available users for assignment (treatment professionals)
        # Include both portal and internal treatment professionals.
        portal_tp_group = request.env.ref('bemade_sports_clinic.group_portal_treatment_professional')
        internal_tp_group = request.env.ref('bemade_sports_clinic.group_sports_clinic_treatment_professional')
        available_users = request.env['res.users'].search([
            ('groups_id', 'in', [portal_tp_group.id, internal_tp_group.id])
        ])
        
        from datetime import date
        
        values = {
            'activity': activity,
            'activity_types': activity_types,
            'available_users': available_users,
            'page_name': 'edit_activity',
            'today': date.today().strftime('%Y-%m-%d'),
        }
        
        return request.render('bemade_sports_clinic.portal_edit_activity', values)

    @http.route(['/my/activity/<int:activity_id>'], type='http', auth='user', website=True)
    def view_activity_detail(self, activity_id, **kw):
        """Display detailed view of a specific activity"""
        activity = request.env['mail.activity'].browse(activity_id)
        
        # Check if the activity exists and user has access to it
        if not activity.exists():
            raise request.not_found()
            
        # Check access permissions (user assigned to activity or related to patient/injury through teams)
        user = request.env.user
        partner = user.partner_id
        
        # Allow access if user is assigned to the activity
        if activity.user_id == user:
            has_access = True
        else:
            # Check if user has access through team relationships
            has_access = False
            if activity.res_model == 'sports.patient':
                patient = request.env['sports.patient'].browse(activity.res_id)
                if patient.exists():
                    # Check if user is staff on any of the patient's teams
                    user_teams = partner.team_staff_rel_ids.mapped('team_id')
                    patient_teams = patient.team_ids
                    has_access = bool(user_teams & patient_teams)
            elif activity.res_model == 'sports.patient.injury':
                injury = request.env['sports.patient.injury'].browse(activity.res_id)
                if injury.exists():
                    # Check if user is staff on any of the injury patient's teams
                    user_teams = partner.team_staff_rel_ids.mapped('team_id')
                    patient_teams = injury.patient_id.team_ids
                    has_access = bool(user_teams & patient_teams)
        
        if not has_access:
            raise request.not_found()
        
        # Get related record details and context for breadcrumbs
        related_record = None
        related_record_name = ''
        context_team = None
        context_patient = None
        context_injury = None
        context_event = None

        if activity.res_model and activity.res_id:
            try:
                related_record = request.env[activity.res_model].browse(activity.res_id)
                if related_record.exists():
                    if activity.res_model == 'sports.patient':
                        context_patient = related_record
                        related_record_name = f"{related_record.first_name} {related_record.last_name}"
                    elif activity.res_model == 'sports.patient.injury':
                        context_injury = related_record
                        context_patient = related_record.patient_id
                        related_record_name = f"{related_record.patient_id.first_name} {related_record.patient_id.last_name} - {related_record.injury_type}"
                    elif activity.res_model == 'sports.team':
                        context_team = related_record
                        related_record_name = related_record.display_name
                    elif activity.res_model == 'sports.event':
                        context_event = related_record
                        related_record_name = related_record.display_name
                    else:
                        related_record_name = related_record.display_name
            except Exception:
                pass
        
        # Get attachments for this activity
        attachments = request.env['ir.attachment'].search([
            ('res_model', '=', 'mail.activity'),
            ('res_id', '=', activity.id)
        ])
        
        from datetime import date
        
        values = {
            'activity': activity,
            'related_record': related_record,
            'related_record_name': related_record_name,
            'attachments': attachments,
            'page_name': 'activity_detail',
            'today': date.today().strftime('%Y-%m-%d'),
            'context_team': context_team,
            'context_patient': context_patient,
            'context_injury': context_injury,
            'context_event': context_event,
        }
        
        return request.render('bemade_sports_clinic.portal_activity_detail', values)
    
    @http.route(['/my/messages'], type='http', auth='user', website=True)
    def view_messages(self, model=None, res_id=None, **kw):
        """Display list of messages accessible to the current user through team relationships"""
        user = request.env.user
        partner = user.partner_id
        
        team_staff_rels = partner.team_staff_rel_ids
        
        # Build team-based access domain for security filtering
        team_access_domain = [
            '|', '|',
            '&', '&',
            ('model', '=', 'sports.patient'),
            ('res_id', '!=', False),
            ('res_id', 'in', team_staff_rels.mapped('team_id.patient_ids.id') or [0]),
            '&', '&',
            ('model', '=', 'sports.patient.injury'),
            ('res_id', '!=', False),
            ('res_id', 'in', team_staff_rels.mapped('team_id.patient_ids.injury_ids.id') or [0]),
            '&', '&',
            ('model', '=', 'sports.team'),
            ('res_id', '!=', False),
            ('res_id', 'in', team_staff_rels.mapped('team_id.id') or [0])
        ]
        
        # Combine with model/res_id filtering if specified
        if model:
            domain = [
                '&',
                ('model', '=', model),
            ] + team_access_domain

            if res_id:
                domain = [
                    '&',
                    ('res_id', '=', int(res_id)),
                ] + domain

        else:
            domain = team_access_domain
        
        # Search for messages with team-based access control
        messages = request.env['mail.message'].search(domain, order='date desc')
        
        # Group messages by model
        patient_messages = messages.filtered(lambda m: m.model == 'sports.patient')
        injury_messages = messages.filtered(lambda m: m.model == 'sports.patient.injury')
        team_messages = messages.filtered(lambda m: m.model == 'sports.team')
        
        values = {
            'messages': messages,
            'patient_messages': patient_messages,
            'injury_messages': injury_messages,
            'team_messages': team_messages,
            'page_name': 'messages',
        }
        
        return request.render('bemade_sports_clinic.portal_my_messages', values)
    
    @http.route(['/my/attachments'], type='http', auth='user', website=True)
    def view_attachments(self, model=None, res_id=None, **kw):
        """Display list of attachments accessible to the current user through team relationships"""
        user = request.env.user
        partner = user.partner_id
        
        team_staff_rels = partner.team_staff_rel_ids
        
        # Build team-based access domain for security filtering
        # Include both direct attachments on sports models and activity attachments
        team_access_domain = [
            '|', '|', '|',
            # Direct attachments on sports models
            '&', '&',
            ('res_model', '=', 'sports.patient'),
            ('res_id', '!=', False),
            ('res_id', 'in', team_staff_rels.mapped('team_id.patient_ids.id') or [0]),
            '&', '&',
            ('res_model', '=', 'sports.patient.injury'),
            ('res_id', '!=', False),
            ('res_id', 'in', team_staff_rels.mapped('team_id.patient_ids.injury_ids.id') or [0]),
            '&', '&',
            ('res_model', '=', 'sports.team'),
            ('res_id', '!=', False),
            ('res_id', 'in', team_staff_rels.mapped('team_id.id') or [0]),
            # Attachments on activities related to sports models
            '&', '&',
            ('res_model', '=', 'mail.activity'),
            ('res_id', '!=', False),
            ('res_id', 'in', self._get_accessible_activity_ids(team_staff_rels) or [0])
        ]
        
        # Combine with model/res_id filtering if specified
        if model:
            domain = [
                '&',
                ('res_model', '=', model),
            ] + team_access_domain

            if res_id:
                domain = [
                    '&',
                    ('res_id', '=', int(res_id)),
                ] + domain

        else:
            domain = team_access_domain
        
        # Search for attachments with team-based access control
        attachments = request.env['ir.attachment'].search(domain, order='create_date desc')
        
        # Group attachments by model
        patient_attachments = attachments.filtered(lambda a: a.res_model == 'sports.patient')
        injury_attachments = attachments.filtered(lambda a: a.res_model == 'sports.patient.injury')
        team_attachments = attachments.filtered(lambda a: a.res_model == 'sports.team')
        activity_attachments = attachments.filtered(lambda a: a.res_model == 'mail.activity')
        
        values = {
            'attachments': attachments,
            'patient_attachments': patient_attachments,
            'injury_attachments': injury_attachments,
            'team_attachments': team_attachments,
            'activity_attachments': activity_attachments,
            'page_name': 'attachments',
        }
        
        return request.render('bemade_sports_clinic.portal_my_attachments', values)
    
    def _get_accessible_activity_ids(self, team_staff_rels):
        """Get IDs of activities accessible through team relationships"""
        # Build the same domain used in view_activities
        team_access_domain = [
            '|', '|',
            '&', '&',
            ('res_model', '=', 'sports.patient'),
            ('res_id', '!=', False),
            ('res_id', 'in', team_staff_rels.mapped('team_id.patient_ids.id') or [0]),
            '&', '&',
            ('res_model', '=', 'sports.patient.injury'),
            ('res_id', '!=', False),
            ('res_id', 'in', team_staff_rels.mapped('team_id.patient_ids.injury_ids.id') or [0]),
            '&', '&',
            ('res_model', '=', 'sports.team'),
            ('res_id', '!=', False),
            ('res_id', 'in', team_staff_rels.mapped('team_id.id') or [0])
        ]
        
        activities = request.env['mail.activity'].search(team_access_domain)
        return activities.ids
