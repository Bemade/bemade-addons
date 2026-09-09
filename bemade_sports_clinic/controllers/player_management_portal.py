import logging
from odoo import http, fields, _
from odoo.exceptions import UserError, ValidationError
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager
from .access_control_mixin import AccessControlMixin
from dateutil.relativedelta import relativedelta

_logger = logging.getLogger(__name__)


class PlayerManagementPortal(CustomerPortal, AccessControlMixin):
    """Controller for player management functionality in the portal"""
    
    # Access control methods now inherited from AccessControlMixin
    
    @http.route(['/my/player/create'], type='http', auth='user', website=True)
    def create_player_form(self, **get):
        """Standalone create player with search-first workflow.
        Shows a search UI first; only renders the full create form when a search
        is attempted and yields no matching players.
        """
        user = request.env.user
        is_treatment_prof = request.env.user.has_group('bemade_sports_clinic.group_portal_treatment_professional')
        is_coach = request.env.user.has_group('bemade_sports_clinic.group_portal_team_coach')

        # Gather query params for search-first flow
        first_name = (get.get('first_name') or '').strip()
        last_name = (get.get('last_name') or '').strip()
        dob = (get.get('date_of_birth') or '').strip()
        attempted = any(k in get for k in ('first_name', 'last_name', 'date_of_birth'))
        searched = bool(first_name or last_name or dob)

        # Perform search similar to team add/link, but without team context
        Patient = request.env['sports.patient']
        active_rs = Patient.browse([])
        archived_rs = Patient.browse([])
        if searched and (first_name or last_name):
            like_first = f"%{first_name}%" if first_name else "%"
            like_last = f"%{last_name}%" if last_name else "%"
            domain = [
                ('first_name', 'ilike', like_first),
                ('last_name', 'ilike', like_last),
            ]
            if dob:
                domain.append(('date_of_birth', '=', dob))
            active_rs = Patient.search(domain + [('active', '=', True)], limit=20)
            # Only TPs/admins can see archived
            if is_treatment_prof or request.env.user.has_group('base.group_system'):
                archived_rs = Patient.with_context(active_test=False).search(domain + [('active', '=', False)], limit=20)

        def _to_dict(p):
            return {
                'id': p.id,
                'name': p.name,
                'first_name': p.first_name,
                'last_name': p.last_name,
                'date_of_birth': p.date_of_birth or '',
                'active': bool(p.active),
            }

        # Staff-only teams for multi-select
        all_teams = request.env['sports.team'].search([
            ('id', 'in', request.env['sports.team.staff'].search([
                ('partner_id', '=', user.partner_id.id)
            ]).mapped('team_id').ids)
        ], order='name')

        canada = request.env['res.country'].search([('code', '=', 'CA')], limit=1)
        states = request.env['res.country.state'].search([('country_id', '=', canada.id)], order='name') if canada else request.env['res.country.state']
        countries = canada if canada else request.env['res.country'].search([], order='name')

        values = self._prepare_portal_layout_values()
        values.update({
            'page_name': 'create_player',
            'is_treatment_prof': is_treatment_prof,
            'is_coach': is_coach,
            'all_teams': all_teams,
            'states': states,
            'countries': countries,
            'relationship_types': request.env['sports.patient.contact']._fields['contact_type'].selection,
            # search-first context
            'first_name': first_name,
            'last_name': last_name,
            'date_of_birth': dob,
            'attempted': attempted,
            'searched': searched,
            'active_results': [_to_dict(p) for p in active_rs],
            'archived_results': [_to_dict(p) for p in archived_rs],
        })
        if attempted and not searched:
            values['error'] = _('Provide at least a first or last name to search')
        return request.render('bemade_sports_clinic.portal_create_player', values)

    @http.route(['/my/player/create/save'], type='http', auth='user', website=True, methods=['POST'])
    def create_player_submit(self, **post):
        """Handle standalone player creation submit."""
        user = request.env.user
        is_treatment_prof = user.has_group('bemade_sports_clinic.group_portal_treatment_professional')
        is_coach = user.has_group('bemade_sports_clinic.group_portal_team_coach')

        first_name = (post.get('first_name') or '').strip()
        last_name = (post.get('last_name') or '').strip()
        dob = (post.get('date_of_birth') or '').strip()

        if not first_name or not last_name:
            request.session['notification'] = {
                'type': 'danger',
                'message': _('First name and last name are required')
            }
            return request.redirect('/my/player/create')

        # Team selection (optional). Restrict to staff teams to avoid tampering
        try:
            selected_team_ids = [int(tid) for tid in request.httprequest.form.getlist('team_ids')]
        except Exception:
            selected_team_ids = []
        allowed_team_ids = request.env['sports.team.staff'].search([
            ('partner_id', '=', user.partner_id.id)
        ]).mapped('team_id').ids
        selected_team_ids = [tid for tid in selected_team_ids if tid in allowed_team_ids]

        # Require at least one team for treatment professionals to ensure access control
        if is_treatment_prof and not selected_team_ids:
            canada = request.env['res.country'].search([('code', '=', 'CA')], limit=1)
            states = request.env['res.country.state'].search([('country_id', '=', canada.id)], order='name') if canada else request.env['res.country.state']
            countries = canada if canada else request.env['res.country'].search([], order='name')
            all_teams = request.env['sports.team'].search([
                ('id', 'in', request.env['sports.team.staff'].search([
                    ('partner_id', '=', user.partner_id.id)
                ]).mapped('team_id').ids)
            ], order='name')

            values = self._prepare_portal_layout_values()
            values.update({
                'page_name': 'create_player',
                'is_treatment_prof': is_treatment_prof,
                'is_coach': is_coach,
                'all_teams': all_teams,
                'states': states,
                'countries': countries,
                'relationship_types': request.env['sports.patient.contact']._fields['contact_type'].selection,
                # keep the original search context so the create form shows
                'first_name': first_name,
                'last_name': last_name,
                'date_of_birth': dob,
                'attempted': True,
                'searched': True,
                'active_results': [],
                'archived_results': [],
                # provide posted values to prefill the form
                'form_data': dict(post),
                'error': _('Please select at least one team to assign to this player.'),
            })
            return request.render('bemade_sports_clinic.portal_create_player', values)

        # Validate DOB format and range if provided
        if dob:
            try:
                # Will raise if the date is not a valid string for a Date field
                dob_date = fields.Date.to_date(dob)
            except Exception:
                _logger.info('Invalid date_of_birth provided on create: %s', dob)
                canada = request.env['res.country'].search([('code', '=', 'CA')], limit=1)
                states = request.env['res.country.state'].search([('country_id', '=', canada.id)], order='name') if canada else request.env['res.country.state']
                countries = canada if canada else request.env['res.country'].search([], order='name')
                all_teams = request.env['sports.team'].search([
                    ('id', 'in', request.env['sports.team.staff'].search([
                        ('partner_id', '=', user.partner_id.id)
                    ]).mapped('team_id').ids)
                ], order='name')

                values = self._prepare_portal_layout_values()
                values.update({
                    'page_name': 'create_player',
                    'is_treatment_prof': is_treatment_prof,
                    'all_teams': all_teams,
                    'states': states,
                    'countries': countries,
                    'relationship_types': request.env['sports.patient.contact']._fields['contact_type'].selection,
                    # keep the original search context so the create form shows
                    'first_name': first_name,
                    'last_name': last_name,
                    'date_of_birth': dob,
                    'attempted': True,
                    'searched': True,
                    'active_results': [],
                    'archived_results': [],
                    # provide posted values to prefill the form
                    'form_data': dict(post),
                    'error': _('Please enter a valid Date of Birth (YYYY-MM-DD).'),
                })
                return request.render('bemade_sports_clinic.portal_create_player', values)

            # Range checks: not in the future, not older than 120 years
            today = fields.Date.context_today(request.env.user) or fields.Date.today()
            min_dob = today - relativedelta(years=120)
            if dob_date > today or dob_date < min_dob:
                canada = request.env['res.country'].search([('code', '=', 'CA')], limit=1)
                states = request.env['res.country.state'].search([('country_id', '=', canada.id)], order='name') if canada else request.env['res.country.state']
                countries = canada if canada else request.env['res.country'].search([], order='name')
                all_teams = request.env['sports.team'].search([
                    ('id', 'in', request.env['sports.team.staff'].search([
                        ('partner_id', '=', user.partner_id.id)
                    ]).mapped('team_id').ids)
                ], order='name')

                values = self._prepare_portal_layout_values()
                values.update({
                    'page_name': 'create_player',
                    'is_treatment_prof': is_treatment_prof,
                    'all_teams': all_teams,
                    'states': states,
                    'countries': countries,
                    'relationship_types': request.env['sports.patient.contact']._fields['contact_type'].selection,
                    # keep the original search context so the create form shows
                    'first_name': first_name,
                    'last_name': last_name,
                    'date_of_birth': dob,
                    'attempted': True,
                    'searched': True,
                    'active_results': [],
                    'archived_results': [],
                    # provide posted values to prefill the form
                    'form_data': dict(post),
                    'error': _('Date of Birth must not be in the future and not be more than 120 years ago.'),
                })
                return request.render('bemade_sports_clinic.portal_create_player', values)

        vals = {
            'first_name': first_name,
            'last_name': last_name,
        }
        if dob:
            vals['date_of_birth'] = dob
        # Optional contact and address fields
        for key in ['email', 'phone', 'street', 'street2', 'city', 'zip']:
            if key in post:
                vals[key] = post.get(key) or False
        if post.get('state_id'):
            try:
                vals['state_id'] = int(post.get('state_id'))
            except Exception:
                pass
        if post.get('country_id'):
            try:
                vals['country_id'] = int(post.get('country_id'))
            except Exception:
                pass

        # Additional fields for treatment professionals
        if is_treatment_prof:
            if selected_team_ids:
                vals['team_ids'] = [(6, 0, list(set(selected_team_ids)))]
            if 'allergies' in post:
                _all = (post.get('allergies') or '').strip()
                vals['allergies'] = _all if _all else False
            if 'team_info_notes' in post:
                _notes = (post.get('team_info_notes') or '').strip()
                vals['team_info_notes'] = _notes if _notes else False
            if post.get('match_status'):
                vals['match_status'] = post.get('match_status')
            if post.get('practice_status'):
                vals['practice_status'] = post.get('practice_status')

        # Use public create method with permission checks
        try:
            patient = request.env['sports.patient'].create_portal_patient(vals)
        except ValidationError as ve:
            # Re-render the create form (search-first view) with preserved input and a friendly message
            _logger.info('ValidationError during player create: %s', ve)
            # Rebuild the context needed by the search-first page
            canada = request.env['res.country'].search([('code', '=', 'CA')], limit=1)
            states = request.env['res.country.state'].search([('country_id', '=', canada.id)], order='name') if canada else request.env['res.country.state']
            countries = canada if canada else request.env['res.country'].search([], order='name')
            all_teams = request.env['sports.team'].search([
                ('id', 'in', request.env['sports.team.staff'].search([
                    ('partner_id', '=', user.partner_id.id)
                ]).mapped('team_id').ids)
            ], order='name')

            values = self._prepare_portal_layout_values()
            values.update({
                'page_name': 'create_player',
                'is_treatment_prof': is_treatment_prof,
                'all_teams': all_teams,
                'states': states,
                'countries': countries,
                'relationship_types': request.env['sports.patient.contact']._fields['contact_type'].selection,
                # keep the original search context so the create form shows
                'first_name': first_name,
                'last_name': last_name,
                'date_of_birth': dob,
                'attempted': True,
                'searched': True,
                'active_results': [],
                'archived_results': [],
                # provide posted values to prefill the form
                'form_data': dict(post),
                'error': str(ve) or _('Invalid combination of match and practice status.'),
            })
            return request.render('bemade_sports_clinic.portal_create_player', values)
        except Exception as e:
            # Render the create form with a generic error and preserve inputs
            _logger.exception('Error creating patient from portal create')
            canada = request.env['res.country'].search([('code', '=', 'CA')], limit=1)
            states = request.env['res.country.state'].search([('country_id', '=', canada.id)], order='name') if canada else request.env['res.country.state']
            countries = canada if canada else request.env['res.country'].search([], order='name')
            all_teams = request.env['sports.team'].search([
                ('id', 'in', request.env['sports.team.staff'].search([
                    ('partner_id', '=', user.partner_id.id)
                ]).mapped('team_id').ids)
            ], order='name')

            values = self._prepare_portal_layout_values()
            values.update({
                'page_name': 'create_player',
                'is_treatment_prof': is_treatment_prof,
                'all_teams': all_teams,
                'states': states,
                'countries': countries,
                'relationship_types': request.env['sports.patient.contact']._fields['contact_type'].selection,
                # keep the original search context so the create form shows
                'first_name': first_name,
                'last_name': last_name,
                'date_of_birth': dob,
                'attempted': True,
                'searched': True,
                'active_results': [],
                'archived_results': [],
                # provide posted values to prefill the form
                'form_data': dict(post),
                'error': str(e) or _('There was an error creating the player. Please review your inputs and try again.'),
            })
            return request.render('bemade_sports_clinic.portal_create_player', values)

        # Optionally create a primary emergency contact if provided (TPs and coaches)
        if is_treatment_prof or is_coach:
            ec_name = (post.get('ec_name') or '').strip()
            ec_type = (post.get('ec_contact_type') or '').strip()
            if ec_name and ec_type:
                contact_vals = {
                    'patient_id': patient.id,
                    'name': ec_name,
                    'contact_type': ec_type,
                }
                if post.get('ec_mobile'):
                    contact_vals['mobile'] = post.get('ec_mobile')
                if post.get('ec_email'):
                    contact_vals['email'] = post.get('ec_email')
                try:
                    request.env['sports.patient.contact'].sudo().create(contact_vals)
                except Exception:
                    _logger.exception('Failed to create primary emergency contact during player create')

        return request.redirect(f"/my/player?player_id={patient.id}")
    
    @http.route(['/my/player/edit'], type='http', auth='user', website=True)
    def edit_player_form(self, patient_id, **post):
        """Show form to edit player information"""
        try:
            patient = self._check_access_to_patient(patient_id)
        except UserError as e:
            response = request.render('http_routing.http_error', {
                'status_code': 403,
                'status_message': 'Forbidden',
                'error_message': str(e),
            })
            response.status_code = 403
            return response
        
        # Check if user is a treatment professional or coach
        user = request.env.user
        is_treatment_prof = user.has_group('bemade_sports_clinic.group_portal_treatment_professional')
        is_coach = user.has_group('bemade_sports_clinic.group_portal_team_coach')
        
        teams = patient.team_ids
        # All teams for multi-select limited to current user's staff teams
        all_teams = request.env['sports.team'].search([
            ('id', 'in', request.env['sports.team.staff'].search([
                ('partner_id', '=', user.partner_id.id)
            ]).mapped('team_id').ids)
        ], order='name')
        
        # Determine team context from query or post and whether a coach can request removal
        # Only consider a team context if the current user is staff on that team and the player is a member
        raw_team_ctx = request.httprequest.args.get('team_id') or post.get('team_id')
        team_context_id = None
        team = None
        if raw_team_ctx:
            try:
                cand_id = int(raw_team_ctx)
                # Validate access via shared mixin helper
                team_obj = self._check_team_access(cand_id, check_staff=True)
                if team_obj and team_obj in teams:
                    team_context_id = cand_id
                    team = team_obj
            except Exception:
                # Ignore invalid team context silently
                team_context_id = None

        # Compute removal visibility/target for coaches
        player_team_count = len(teams)
        can_request_removal = bool(is_coach and ((team_context_id is not None) or (player_team_count == 1)))
        removal_team_id = None
        if can_request_removal:
            if team_context_id is not None:
                removal_team_id = team_context_id
            elif player_team_count == 1:
                removal_team_id = teams[0].id
        
        # Build default return_url based on validated team context if not explicitly provided
        return_url = post.get('return_url') or request.httprequest.args.get('return_url')
        if not return_url:
            if team_context_id is not None:
                return_url = f'/my/player?player_id={patient_id}&team_id={team_context_id}'
            else:
                return_url = f'/my/player?player_id={patient_id}'

        # Create a dictionary with patient info for protected fields
        patient_info = {}
        
        # Only include protected fields if user has appropriate permissions
        if is_treatment_prof:
            # Access fields directly - field-level security is already defined
            # with appropriate groups for each field
            
            # Additional fields available to treatment professionals
            
            # Basic fields
            patient_info['date_of_birth'] = patient.date_of_birth
            patient_info['age'] = patient.age
            patient_info['allergies'] = patient.allergies
            patient_info['team_info_notes'] = patient.team_info_notes
            
            # Status fields
            patient_info['match_status'] = patient.match_status
            patient_info['practice_status'] = patient.practice_status
            patient_info['last_consultation_date'] = patient.last_consultation_date
            
            # Injury tracking fields
            patient_info['injured_since'] = patient.injured_since
            
            # Add any other protected fields that should be available to treatment professionals
            # You can add more fields here as needed
            
            # Patient info prepared for treatment professional view
        
        # Get Canada and Canadian provinces/territories for address dropdowns
        canada = request.env['res.country'].search([('code', '=', 'CA')], limit=1)
        states = request.env['res.country.state'].search([('country_id', '=', canada.id)], order='name') if canada else request.env['res.country.state']
        countries = canada if canada else request.env['res.country'].search([], order='name')
        # Determine primary emergency contact (lowest sequence)
        primary_contact = request.env['sports.patient.contact'].search([
            ('patient_id', '=', patient.id)
        ], order='sequence,id', limit=1)
        
        values = {
            'patient': patient,  # Keep original patient
            'patient_info': patient_info,  # Add patient_info for protected fields
            'teams': teams,
            'all_teams': all_teams,
            'states': states,
            'countries': countries,
            'relationship_types': request.env['sports.patient.contact']._fields['contact_type'].selection,
            # Primary emergency contact defaults for prefill
            'ec_name': primary_contact.name if primary_contact else '',
            'ec_contact_type': primary_contact.contact_type if primary_contact else '',
            'ec_mobile': primary_contact.mobile if primary_contact else '',
            'ec_email': primary_contact.email if primary_contact else '',
            'return_url': return_url,
            'page_name': 'edit_player',
            'is_treatment_prof': is_treatment_prof,
            'is_coach': is_coach,
            # Coach removal request context
            'can_request_removal': can_request_removal,
            'removal_team_id': removal_team_id,
            'team_context_id': team_context_id,
            'team': team,
        }
        
        return request.render('bemade_sports_clinic.portal_edit_player', values)
    
    @http.route(['/my/player/save'], type='http', auth='user', website=True, methods=['POST'])
    def edit_player_submit(self, **post):
        """Process the form submission to update player information"""
        patient_id = post.get('patient_id')
        
        if not patient_id:
            return request.redirect('/my/players')
            
        try:
            patient = self._check_access_to_patient(patient_id)
        except UserError as e:
            response = request.render('http_routing.http_error', {
                'status_code': 403,
                'status_message': 'Forbidden',
                'error_message': str(e),
            })
            response.status_code = 403
            return response
            
        # Check if user is a treatment professional or coach
        is_treatment_prof = request.env.user.has_group('bemade_sports_clinic.group_portal_treatment_professional')
        is_coach = request.env.user.has_group('bemade_sports_clinic.group_portal_team_coach')
        
        # If DOB is being changed/provided, validate format upfront to avoid unhelpful errors
        dob_str = (post.get('date_of_birth') or '').strip()
        if dob_str:
            try:
                dob_date = fields.Date.to_date(dob_str)
            except Exception:
                # Rebuild dropdowns and re-render with preserved inputs
                user = request.env.user
                canada = request.env['res.country'].search([('code', '=', 'CA')], limit=1)
                states = request.env['res.country.state'].search([('country_id', '=', canada.id)], order='name') if canada else request.env['res.country.state']
                countries = canada if canada else request.env['res.country'].search([], order='name')
                all_teams = request.env['sports.team'].search([
                    ('id', 'in', request.env['sports.team.staff'].search([
                        ('partner_id', '=', user.partner_id.id)
                    ]).mapped('team_id').ids)
                ], order='name')

                values = {
                    'patient': patient,
                    'patient_info': {},
                    'teams': patient.team_ids,
                    'all_teams': all_teams,
                    'states': states,
                    'countries': countries,
                    'relationship_types': request.env['sports.patient.contact']._fields['contact_type'].selection,
                    'return_url': post.get('return_url', f'/my/player?player_id={patient_id}'),
                    'page_name': 'edit_player',
                    'is_treatment_prof': is_treatment_prof,
                    'is_coach': is_coach,
                    'error': _('Please enter a valid Date of Birth (YYYY-MM-DD).'),
                    'form_data': dict(post),
                }
                return request.render('bemade_sports_clinic.portal_edit_player', values)

            # Range checks: not in the future, not older than 120 years
            today = fields.Date.context_today(request.env.user) or fields.Date.today()
            min_dob = today - relativedelta(years=120)
            if dob_date > today or dob_date < min_dob:
                user = request.env.user
                canada = request.env['res.country'].search([('code', '=', 'CA')], limit=1)
                states = request.env['res.country.state'].search([('country_id', '=', canada.id)], order='name') if canada else request.env['res.country.state']
                countries = canada if canada else request.env['res.country'].search([], order='name')
                all_teams = request.env['sports.team'].search([
                    ('id', 'in', request.env['sports.team.staff'].search([
                        ('partner_id', '=', user.partner_id.id)
                    ]).mapped('team_id').ids)
                ], order='name')

                values = {
                    'patient': patient,
                    'patient_info': {},
                    'teams': patient.team_ids,
                    'all_teams': all_teams,
                    'states': states,
                    'countries': countries,
                    'relationship_types': request.env['sports.patient.contact']._fields['contact_type'].selection,
                    'return_url': post.get('return_url', f'/my/player?player_id={patient_id}'),
                    'page_name': 'edit_player',
                    'is_treatment_prof': is_treatment_prof,
                    'is_coach': is_coach,
                    'error': _('Date of Birth must not be in the future and not be more than 120 years ago.'),
                    'form_data': dict(post),
                }
                return request.render('bemade_sports_clinic.portal_edit_player', values)

        # Prepare values for patient update
        vals = {}
        
        # Basic information - any portal user with access can update these
        if post.get('first_name') and post.get('last_name'):
            vals.update({
                'first_name': post.get('first_name'),
                'last_name': post.get('last_name'),
            })
            
        # Contact information
        if post.get('email'):
            vals.update({
                'email': post.get('email'),
            })
            
        if post.get('phone'):
            vals.update({
                'phone': post.get('phone'),
            })
            
        # Address information - any portal user with access can update these
        address_fields = ['street', 'street2', 'city', 'zip']
        for field in address_fields:
            if field in post:
                vals[field] = post.get(field) or False
                
        # Handle state and country selections
        if post.get('state_id'):
            try:
                state_id = int(post.get('state_id'))
                vals['state_id'] = state_id
            except (ValueError, TypeError):
                pass  # Invalid state_id, skip
                
        if post.get('country_id'):
            try:
                country_id = int(post.get('country_id'))
                vals['country_id'] = country_id
            except (ValueError, TypeError):
                pass  # Invalid country_id, skip
            
        # Additional fields that only treatment professionals can update
        if is_treatment_prof:
            # Team assignments via multi-select
            try:
                team_id_list = [int(tid) for tid in request.httprequest.form.getlist('team_ids')]
            except Exception:
                team_id_list = []
            # Defense-in-depth: restrict to teams where current user is staff
            allowed_team_ids = request.env['sports.team.staff'].search([
                ('partner_id', '=', request.env.user.partner_id.id)
            ]).mapped('team_id').ids
            filtered_team_ids = [tid for tid in team_id_list if tid in allowed_team_ids]
            # Always set the M2M command, even if empty, to allow clearing all teams
            vals['team_ids'] = [(6, 0, list(set(filtered_team_ids)))]
            if post.get('date_of_birth'):
                vals.update({
                    'date_of_birth': post.get('date_of_birth'),
                })
                
            # Medical information
            if 'allergies' in post:
                _all = (post.get('allergies') or '').strip()
                vals.update({
                    'allergies': _all if _all else False,
                })
                
            if 'team_info_notes' in post:
                _notes = (post.get('team_info_notes') or '').strip()
                vals.update({
                    'team_info_notes': _notes if _notes else False,
                })
                
            # Status fields
            if post.get('match_status'):
                vals.update({
                    'match_status': post.get('match_status'),
                })
                
            if post.get('practice_status'):
                vals.update({
                    'practice_status': post.get('practice_status'),
                })

            if 'last_consultation_date' in post:
                _lcd = (post.get('last_consultation_date') or '').strip()
                vals['last_consultation_date'] = _lcd if _lcd else False
        
        # Update the patient - no sudo needed as field-level security is in place
        if vals:
            try:
                patient.write(vals)
            except ValidationError as ve:
                # Re-render edit form with preserved input and error
                user = request.env.user
                is_treatment_prof = user.has_group('bemade_sports_clinic.group_portal_treatment_professional')
                canada = request.env['res.country'].search([('code', '=', 'CA')], limit=1)
                states = request.env['res.country.state'].search([('country_id', '=', canada.id)], order='name') if canada else request.env['res.country.state']
                countries = canada if canada else request.env['res.country'].search([], order='name')
                # All teams for multi-select limited to current user's staff teams
                all_teams = request.env['sports.team'].search([
                    ('id', 'in', request.env['sports.team.staff'].search([
                        ('partner_id', '=', user.partner_id.id)
                    ]).mapped('team_id').ids)
                ], order='name')

                values = {
                    'patient': patient,
                    'patient_info': {},
                    'teams': patient.team_ids,
                    'all_teams': all_teams,
                    'states': states,
                    'countries': countries,
                    'relationship_types': request.env['sports.patient.contact']._fields['contact_type'].selection,
                    'return_url': post.get('return_url', f'/my/player?player_id={patient_id}'),
                    'page_name': 'edit_player',
                    'is_treatment_prof': is_treatment_prof,
                    'is_coach': is_coach,
                    'error': str(ve) or _('Invalid combination of match and practice status.'),
                    'form_data': dict(post),
                }
                return request.render('bemade_sports_clinic.portal_edit_player', values)
            except Exception as e:
                # Generic exception: re-render with generic error and preserved inputs
                user = request.env.user
                is_treatment_prof = user.has_group('bemade_sports_clinic.group_portal_treatment_professional')
                canada = request.env['res.country'].search([('code', '=', 'CA')], limit=1)
                states = request.env['res.country.state'].search([('country_id', '=', canada.id)], order='name') if canada else request.env['res.country.state']
                countries = canada if canada else request.env['res.country'].search([], order='name')
                all_teams = request.env['sports.team'].search([
                    ('id', 'in', request.env['sports.team.staff'].search([
                        ('partner_id', '=', user.partner_id.id)
                    ]).mapped('team_id').ids)
                ], order='name')

                values = {
                    'patient': patient,
                    'patient_info': {},
                    'teams': patient.team_ids,
                    'all_teams': all_teams,
                    'states': states,
                    'countries': countries,
                    'relationship_types': request.env['sports.patient.contact']._fields['contact_type'].selection,
                    'return_url': post.get('return_url', f'/my/player?player_id={patient_id}'),
                    'page_name': 'edit_player',
                    'is_treatment_prof': is_treatment_prof,
                    'is_coach': is_coach,
                    'error': str(e) or _('An unexpected error occurred.'),
                    'form_data': dict(post),
                }
                return request.render('bemade_sports_clinic.portal_edit_player', values)

        # Update or create primary emergency contact (TPs and coaches), regardless of patient field changes
        if is_treatment_prof or is_coach:
            ec_name = (post.get('ec_name') or '').strip()
            ec_type = (post.get('ec_contact_type') or '').strip()
            ec_mobile = (post.get('ec_mobile') or '').strip()
            ec_email = (post.get('ec_email') or '').strip()

            # If any EC field provided, attempt update/create
            if any([ec_name, ec_type, ec_mobile, ec_email]):
                primary_contact = request.env['sports.patient.contact'].search([
                    ('patient_id', '=', patient.id)
                ], order='sequence,id', limit=1)

                if primary_contact:
                    update_vals = {}
                    # Only update name/type if provided (avoid clearing required selection)
                    if ec_name:
                        update_vals['name'] = ec_name
                    if ec_type:
                        update_vals['contact_type'] = ec_type
                    # For mobile/email, explicitly set to value or False to clear
                    if 'ec_mobile' in post:
                        update_vals['mobile'] = ec_mobile or False
                    if 'ec_email' in post:
                        update_vals['email'] = ec_email or False
                    if update_vals:
                        try:
                            primary_contact.sudo().write(update_vals)
                        except Exception:
                            _logger.exception('Failed to update primary emergency contact for patient %s', patient.id)
                else:
                    # Create only if we have minimally required fields
                    if ec_name and ec_type:
                        create_vals = {
                            'patient_id': patient.id,
                            'name': ec_name,
                            'contact_type': ec_type,
                            'sequence': 0,
                        }
                        if 'ec_mobile' in post:
                            create_vals['mobile'] = ec_mobile or False
                        if 'ec_email' in post:
                            create_vals['email'] = ec_email or False
                        try:
                            request.env['sports.patient.contact'].sudo().create(create_vals)
                        except Exception:
                            _logger.exception('Failed to create primary emergency contact for patient %s', patient.id)

        return_url = post.get('return_url') or f'/my/player?player_id={patient_id}'
        return request.redirect(return_url)
    
    @http.route(['/my/player/contact/add'], type='http', auth='user', website=True)
    def add_contact_form(self, patient_id, **post):
        """Show form to add a new emergency contact for a player"""
        try:
            patient = self._check_access_to_patient(patient_id)
        except UserError as e:
            response = request.render('http_routing.http_error', {
                'status_code': 403,
                'status_message': 'Forbidden',
                'error_message': str(e),
            })
            response.status_code = 403
            return response
            
        return_url = post.get('return_url', f'/my/player?player_id={patient_id}')
        
        # Check if user is a treatment professional or coach
        user = request.env.user
        is_treatment_prof = user.has_group('bemade_sports_clinic.group_portal_treatment_professional')
        is_coach = user.has_group('bemade_sports_clinic.group_portal_team_coach')
        
        # Only TPs and coaches can add emergency contacts
        if not (is_treatment_prof or is_coach):
            return request.redirect(return_url)
        
        values = {
            'patient': patient,
            'return_url': return_url,
            'page_name': 'add_contact',
            'relationship_types': request.env['sports.patient.contact']._fields['contact_type'].selection,
        }
        
        return request.render('bemade_sports_clinic.portal_add_contact', values)
    
    @http.route(['/my/player/contact/save'], type='http', auth='user', website=True, methods=['POST'])
    def add_contact_submit(self, **post):
        """Process the form submission to add a new emergency contact"""
        patient_id = post.get('patient_id')
        
        if not patient_id:
            return request.redirect('/my/players')
            
        try:
            patient = self._check_access_to_patient(patient_id)
        except UserError as e:
            response = request.render('http_routing.http_error', {
                'status_code': 403,
                'status_message': 'Forbidden',
                'error_message': str(e),
            })
            response.status_code = 403
            return response
            
        # Check if user is a treatment professional or coach
        is_treatment_prof = request.env.user.has_group('bemade_sports_clinic.group_portal_treatment_professional')
        is_coach = request.env.user.has_group('bemade_sports_clinic.group_portal_team_coach')
        
        # Only TPs and coaches can add emergency contacts
        if not (is_treatment_prof or is_coach):
            return request.redirect(f'/my/player?player_id={patient_id}')
        
        # Required fields
        if not post.get('name') or not post.get('contact_type'):
            values = {
                'patient': patient,
                'error': _("Name and contact type are required fields"),
                'return_url': f'/my/player?player_id={patient_id}',
                'page_name': 'add_contact',
                'relationship_types': request.env['sports.patient.contact']._fields['contact_type'].selection,
            }
            values.update(post)
            return request.render('bemade_sports_clinic.portal_add_contact', values)
        
        # Prepare values for contact creation
        vals = {
            'patient_id': int(patient_id),
            'name': post.get('name'),
            'contact_type': post.get('contact_type'),
        }
        
        # Optional fields
        if post.get('mobile'):
            vals['mobile'] = post.get('mobile')
        if post.get('email'):
            vals['email'] = post.get('email')
        
        # Create the contact
        request.env['sports.patient.contact'].sudo().create(vals)

        # Respect a return_url field so the form lands the user back
        # on the originating tab (e.g. ".../my/player?...#contacts").
        return_url = post.get('return_url') or f'/my/player?player_id={patient_id}#contacts'
        return request.redirect(return_url)
    
    @http.route(['/my/player/contact/edit'], type='http', auth='user', website=True)
    def edit_contact_form(self, contact_id, **post):
        """Show form to edit an existing emergency contact"""
        contact = request.env['sports.patient.contact'].browse(int(contact_id))
        
        if not contact.exists():
            return request.redirect('/my/players')
            
        try:
            patient = self._check_access_to_patient(contact.patient_id.id)
        except UserError as e:
            response = request.render('http_routing.http_error', {
                'status_code': 403,
                'status_message': 'Forbidden',
                'error_message': str(e),
            })
            response.status_code = 403
            return response
            
        return_url = post.get('return_url', f'/my/player?player_id={patient.id}')
        
        # Check if user is a treatment professional or coach
        is_treatment_prof = request.env.user.has_group('bemade_sports_clinic.group_portal_treatment_professional')
        is_coach = request.env.user.has_group('bemade_sports_clinic.group_portal_team_coach')
        
        # Only TPs and coaches can edit emergency contacts
        if not (is_treatment_prof or is_coach):
            return request.redirect(return_url)
        
        values = {
            'patient': patient,
            'contact': contact,
            'return_url': return_url,
            'page_name': 'edit_contact',
            'relationship_types': request.env['sports.patient.contact']._fields['contact_type'].selection,
        }
        
        return request.render('bemade_sports_clinic.portal_edit_contact', values)
    
    @http.route(['/my/player/contact/update'], type='http', auth='user', website=True, methods=['POST'])
    def edit_contact_submit(self, **post):
        """Process the form submission to update an emergency contact"""
        contact_id = post.get('contact_id')
        
        if not contact_id:
            return request.redirect('/my/players')
            
        contact = request.env['sports.patient.contact'].browse(int(contact_id))
        
        if not contact.exists():
            return request.redirect('/my/players')
            
        try:
            patient = self._check_access_to_patient(contact.patient_id.id)
        except UserError as e:
            response = request.render('http_routing.http_error', {
                'status_code': 403,
                'status_message': 'Forbidden',
                'error_message': str(e),
            })
            response.status_code = 403
            return response
            
        # Check if user is a treatment professional
        is_treatment_prof = request.env.user.has_group('bemade_sports_clinic.group_portal_treatment_professional')
        is_coach = request.env.user.has_group('bemade_sports_clinic.group_portal_team_coach')
        
        # Only TPs and coaches can edit emergency contacts
        if not (is_treatment_prof or is_coach):
            return request.redirect(f'/my/player?player_id={patient.id}')
        
        # Required fields
        if not post.get('name') or not post.get('contact_type'):
            values = {
                'patient': patient,
                'contact': contact,
                'error': _("Name and contact type are required fields"),
                'return_url': f'/my/player?player_id={patient.id}',
                'page_name': 'edit_contact',
                'relationship_types': request.env['sports.patient.contact']._fields['contact_type'].selection,
            }
            values.update(post)
            return request.render('bemade_sports_clinic.portal_edit_contact', values)
        
        # Prepare values for contact update
        vals = {
            'name': post.get('name'),
            'contact_type': post.get('contact_type'),
        }
        
        # Optional fields
        if post.get('mobile'):
            vals['mobile'] = post.get('mobile')
        else:
            vals['mobile'] = False
        
        if post.get('email'):
            vals['email'] = post.get('email')
        else:
            vals['email'] = False
        
        # Update the contact
        contact.sudo().write(vals)

        return_url = post.get('return_url') or f'/my/player?player_id={patient.id}#contacts'
        return request.redirect(return_url)
    
    @http.route(['/my/player/contact/delete'], type='http', auth='user', website=True, methods=['POST'])
    def delete_contact(self, contact_id, **post):
        """Delete an emergency contact"""
        contact = request.env['sports.patient.contact'].browse(int(contact_id))
        
        if not contact.exists():
            return request.redirect('/my/players')
            
        try:
            patient = self._check_access_to_patient(contact.patient_id.id)
        except UserError as e:
            response = request.render('http_routing.http_error', {
                'status_code': 403,
                'status_message': 'Forbidden',
                'error_message': str(e),
            })
            response.status_code = 403
            return response
            
        # Check if user is a treatment professional
        is_treatment_prof = request.env.user.has_group('bemade_sports_clinic.group_portal_treatment_professional')
        
        return_url = post.get('return_url') or f'/my/player?player_id={patient.id}#contacts'

        # Regular coaches shouldn't be able to delete emergency contacts
        if not is_treatment_prof:
            return request.redirect(return_url)

        # Delete the contact
        contact.sudo().unlink()

        return request.redirect(return_url)
