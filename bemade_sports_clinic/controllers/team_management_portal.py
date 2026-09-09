from odoo import http, fields, _
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.exceptions import AccessError, MissingError, UserError, ValidationError
from .access_control_mixin import AccessControlMixin
import logging
from datetime import date
from dateutil.relativedelta import relativedelta

_logger = logging.getLogger(__name__)

class TeamManagementPortal(CustomerPortal, AccessControlMixin):
    
    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        return values

    # Access control methods now inherited from AccessControlMixin

    @http.route(['/my/team/<int:team_id>/player/<int:player_id>/request_removal'],
                type='http', auth="user", website=True, methods=['POST'])
    def portal_request_player_removal(self, team_id, player_id, **post):
        """
        Request removal of a player from the team.
        This is used by coaches to request removal, which creates a task for the head therapist.
        """
        try:
            team = self._check_team_access(team_id, check_staff=True)
            patient = request.env['sports.patient'].browse(int(player_id))
            
            if not patient.exists():
                raise MissingError(_("Player not found"))
                
            if team not in patient.team_ids:
                raise ValidationError(_("Player is not a member of this team"))
                
            # Check if there's already a pending removal
            if patient.pending_removal:
                raise ValidationError(_("A removal request is already pending for this player"))
                
            # Get and validate reason
            reason = (post.get('reason') or '').strip()
            if not reason:
                raise ValidationError(_("Please provide a reason for the removal request"))
                
            # Request removal (this will handle the activity creation and logging)
            # No sudo() needed as proper permission checks are in request_team_removal
            patient._request_team_removal(team.id, reason=reason)
            
            # Store success message in session for display after redirect
            request.session['notification'] = {
                'type': 'success',
                'title': _('Removal Request Submitted'),
                'message': _('Your request to remove %s from the team has been submitted for review.') % patient.name,
                'sticky': False,
            }
            
            return request.redirect(f"/my/team/{team_id}")
            
        except Exception as e:
            _logger.error("Error requesting player removal: %s", str(e), exc_info=True)
            error_message = _("Error requesting removal: %s") % str(e)
            return request.redirect(f"/my/team/{team_id}?error={error_message}".replace(' ', '+'))
    
    @http.route(['/my/team/<int:team_id>/player/<int:player_id>/remove'],
               type='http', auth="user", website=True, methods=['POST'])
    def portal_remove_player(self, team_id, player_id, **post):
        """
        Directly remove a player from the team.
        Only accessible by treatment professionals or team staff.
        """
        try:
            team = self._check_team_access(team_id)
            
            # Only treatment professionals or team staff can directly remove
            if not (self._check_treatment_professional_access() or self._check_team_staff_access(team)):
                raise AccessError(_("You don't have permission to remove players from this team."))
                
            patient = request.env['sports.patient'].browse(int(player_id))
            if not patient.exists():
                raise MissingError(_("Player not found"))
                
            if team not in patient.team_ids:
                raise ValidationError(_("Player is not a member of this team"))
                
            # Check if this is a pending removal that's being approved
            is_approving_pending = patient.pending_removal and self._check_treatment_professional_access()
                
            # Process removal with the appropriate action - no sudo needed as remove_from_team has built-in permission checks
            result = patient._remove_from_team(team.id, clear_pending=True)
            
            # Store success message in session for display after redirect
            request.session['notification'] = {
                'type': 'success',
                'title': _('Player Removed'),
                'message': _('%s has been successfully removed from the team.') % patient.sudo().name,
                'sticky': False,
            }
            
            return request.redirect(f"/my/team/{team_id}")
            
        except Exception as e:
            # Don't put the raw exception (often multi-line) in the redirect URL:
            # newlines in a Location header raise a ValueError -> 500. Use a session
            # notification instead, like the success path.
            _logger.error("Error removing player: %s", str(e), exc_info=True)
            request.session['notification'] = {
                'type': 'danger',
                'title': _('Error'),
                'message': _("Could not remove the player. Please try again or contact an administrator."),
                'sticky': False,
            }
            return request.redirect(f"/my/team/{team_id}")
    
    @http.route(['/my/team/<int:team_id>/add_player'],
                type='http', auth="user", website=True)
    def portal_add_player_form(self, team_id, **kw):
        """Display the form to add a new player to a team."""
        try:
            team = self._check_team_access(team_id)
            values = self._prepare_portal_layout_values()
            
            # Check for success/error messages
            success = request.httprequest.args.get('success')
            if success == 'player_reactivated':
                values['success'] = _("An archived player was found and reactivated, and has been added to this team.")
            elif success == 'player_added_to_team':
                values['success'] = _("An existing player was found and has been added to this team.")
            elif success == 'player_created':
                values['success'] = _("A new player has been created and added to the team.")
            
            values.update({
                'team': team,
                'page_name': 'add_player',
                'error': request.httprequest.args.get('error'),
            })
            
            # Preserve form data if there was an error
            if kw.get('error'):
                values.update({
                    'first_name': kw.get('first_name', ''),
                    'last_name': kw.get('last_name', ''),
                    'email': kw.get('email', ''),
                    'phone': kw.get('phone', ''),
                    'date_of_birth': kw.get('date_of_birth', ''),
                })
                
            return request.render("bemade_sports_clinic.portal_add_player", values)
            
        except (AccessError, MissingError) as e:
            return request.redirect('/my')
        except Exception as e:
            _logger.exception("Error in portal_add_player_form")
            values = request.params.copy()
            values['error'] = _("An error occurred while loading the form. Please try again.")
            return request.render("bemade_sports_clinic.portal_add_player", values)

    @http.route(['/my/team', '/my/team/<int:team_id>'], type='http', auth="user", website=True)
    def portal_team_players(self, team_id=None, **kw):
        """Display the list of players for a team.

        Canonical public URL shape is /my/team?team_id=<id> to align with
        breadcrumbs and other portal links. The route also accepts
        /my/team/<int:team_id> but all redirects and templates should use
        the query-string form.
        """
        try:
            if not team_id:
                # If no team_id is provided in the path, fall back to query string
                team_id = request.httprequest.args.get('team_id')
                if not team_id:
                    # If still no team_id, redirect to the teams list
                    return request.redirect('/my/teams')

            team = self._check_team_access(team_id)
            
            # Get all players for the team, sorted by status severity so the
            # most concerning players (injured/limited) surface first, then by name.
            players = request.env['sports.patient'].search([
                ('team_ids', 'in', [team.id]),
                ('active', '=', True)
            ], order='last_name, first_name')
            stage_priority = {'no_play': 0, 'practice_ok': 1, 'healthy': 2}
            players = players.sorted(
                key=lambda p: (
                    stage_priority.get(p.stage, 99),
                    (p.last_name or '').lower(),
                    (p.first_name or '').lower(),
                )
            )
            
            # Check user permissions for UI elements
            is_treatment_prof = request.env.user.has_group(
                'bemade_sports_clinic.group_portal_treatment_professional')
            is_admin = request.env.user.has_group('base.group_system')
            is_team_staff = team.staff_ids.filtered(
                lambda s: request.env.user.partner_id in s.user_ids.partner_id
            )
            
            values = {
                # Use my_teams so existing breadcrumbs logic renders
                # "Teams / <Team Name>" for team detail pages.
                'page_name': 'my_teams',
                'team': team,
                'players': players,
                # Canonical URL used by pager and templates
                'default_url': f'/my/team?team_id={team.id}',
                'user_has_group': request.env.user.has_group,  # Pass the has_group method to template
                'user': request.env.user,
                'is_treatment_prof': is_treatment_prof or is_admin,
                'is_team_staff': bool(is_team_staff),
            }
            
            # Add success/error messages if present in the URL
            success = request.httprequest.args.get('success')
            error = request.httprequest.args.get('error')
            
            if success == 'player_removed':
                values['success'] = _("Player has been successfully removed from the team.")
            elif success == 'removal_requested':
                values['success'] = _("A request to remove this player has been submitted to the head therapist.")
            elif success == 'player_reactivated':
                values['success'] = _("An archived player was found and reactivated, and has been added to this team.")
            elif success == 'player_added_to_team':
                values['success'] = _("Player has been added to the team.")
                
            if error:
                values['error'] = error
            
            return request.render('bemade_sports_clinic.portal_my_team_players', values)
            
        except (AccessError, MissingError) as e:
            return request.redirect('/my/teams?error=%s' % str(e))

    def _find_existing_patient(self, first_name, last_name, email=None, phone=None):
        """Search for an existing patient by name and contact information.

        Task 640: for TPs/admins the lookup is done sudo so unteamed patients
        hidden by per-record ir.rules can still be found (and subsequently linked
        to a team). Coaches keep the rule-scoped, active-only behaviour.
        """
        is_tp_admin = request.env.user.has_group('bemade_sports_clinic.group_portal_treatment_professional') or \
            request.env.user.has_group('base.group_system')
        Patient = request.env['sports.patient'].sudo() if is_tp_admin else request.env['sports.patient']
        domain = [
            ('first_name', '=ilike', first_name.strip()),
            ('last_name', '=ilike', last_name.strip()),
            '|',
            ('active', '=', True),
            ('active', '=', False),  # Include inactive to handle archived players
        ]
        
        # Additional search criteria if email or phone is provided
        if email and email.strip():
            domain = ['|'] + domain + [
                '&',
                ('partner_id.email', '=ilike', email.strip()),
                ('partner_id.email', '!=', False)
            ]
        if phone and phone.strip():
            domain = ['|'] + domain + [
                '&',
                ('partner_id.phone', '=', phone.strip()),
                ('partner_id.phone', '!=', False)
            ]
        
        # Search active records first. For TPs/admins Patient is sudo (see above),
        # so unteamed/rule-hidden patients are found; coaches stay rule-scoped.
        active_patient = Patient.search(domain + [('active', '=', True)], limit=1)
        if active_patient:
            return active_patient

        # Archived records are only relevant to treatment professionals / admins.
        if is_tp_admin:
            return Patient.search(domain + [('active', '=', False)], limit=1)

        return request.env['sports.patient'].browse([])  # Empty recordset if no matches

    @http.route(['/my/team/<int:team_id>/player/add_link'], type='http', auth='user', website=True, methods=['GET'])
    def portal_add_link_player_page(self, team_id, **get):
        """Render a dedicated page to search and add/link a player to the team.
        Server-rendered search results avoid fragile modal JS.
        """
        try:
            team = self._check_team_access(team_id)

            # Only therapists/admins can add directly; others should use request flow
            if not (request.env.user.has_group('bemade_sports_clinic.group_portal_treatment_professional') or
                    request.env.user.has_group('base.group_system')):
                request.session['notification'] = {
                    'type': 'danger',
                    'title': _('Access Denied'),
                    'message': _("You don't have permission to add players. You may submit a request instead."),
                    'sticky': False,
                }
                return request.redirect(f"/my/team/{team.id}")

            # Gather query params
            first_name = (get.get('first_name') or '').strip()
            last_name = (get.get('last_name') or '').strip()
            dob = (get.get('date_of_birth') or '').strip()
            # Consider a search attempted if the query params include any of the fields,
            # even if empty (user pressed Search without filling fields)
            attempted = any(k in get for k in ('first_name', 'last_name', 'date_of_birth'))
            # Trigger search when at least one identifier is provided
            searched = bool(first_name or last_name or dob)

            # Perform search when query present
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
                # Task 640: this route is already restricted to TPs/admins above, who
                # must be able to FIND any patient by name/DOB to add them to a team -
                # including unteamed patients that the per-record ir.rules would hide.
                # sudo() the identity-level lookup; only name/DOB are surfaced (see
                # _to_dict). Full record access stays rule-gated elsewhere.
                active_rs = Patient.sudo().search(domain + [('active', '=', True)], limit=20)
                archived_rs = Patient.sudo().with_context(active_test=False).search(domain + [('active', '=', False)], limit=20)

            def _to_dict(p):
                return {
                    'id': p.id,
                    'name': p.name,
                    'first_name': p.first_name,
                    'last_name': p.last_name,
                    'date_of_birth': p.date_of_birth or '',
                    'active': bool(p.active),
                    'on_team': team in p.team_ids,
                }

            values = self._prepare_portal_layout_values()
            values.update({
                'page_name': 'add_link_player',
                'team': team,
                'first_name': first_name,
                'last_name': last_name,
                'date_of_birth': dob,
                'searched': searched,
                'active_results': [_to_dict(p) for p in active_rs],
                'archived_results': [_to_dict(p) for p in archived_rs],
                # Extra context to support inline full create form
                'is_treatment_prof': request.env.user.has_group('bemade_sports_clinic.group_portal_treatment_professional') or request.env.user.has_group('base.group_system'),
                'states': request.env['res.country.state'].search([('country_id.code', '=', 'CA')], order='name'),
                'countries': request.env['res.country'].search([('code', '=', 'CA')], limit=1) or request.env['res.country'].search([], order='name'),
                'all_teams': request.env['sports.team'].search([
                    ('id', 'in', request.env['sports.team.staff'].search([
                        ('partner_id', '=', request.env.user.partner_id.id)
                    ]).mapped('team_id').ids)
                ], order='name'),
                'relationship_types': request.env['sports.patient.contact']._fields['contact_type'].selection,
                'prefill_team_id': team.id,
            })
            if attempted and not searched:
                values['error'] = _('Provide at least a first or last name to search')
            return request.render('bemade_sports_clinic.portal_add_link_player_page', values)
        except (AccessError, MissingError):
            return request.redirect('/my/teams')
        except Exception:
            _logger.exception('Error rendering add/link player page')
            request.session['notification'] = {
                'type': 'danger',
                'title': _('Error'),
                'message': _('Unable to open Add/Link Player page right now.'),
                'sticky': False,
            }
            return request.redirect(f"/my/team/{team_id}")

    @http.route(['/my/team/<int:team_id>/player/create_full'], type='http', auth='user', website=True, methods=['POST'], csrf=True)
    def portal_create_player_full(self, team_id, **post):
        """Create a brand new player with full details (inline edit form) and link to team.
        This is used when the search yields no results and we render the full form inline.
        Only treatment professionals/admins may create directly.
        """
        try:
            team = self._check_team_access(team_id)

            # Permission: only therapists/admins can create directly
            is_tp = request.env.user.has_group('bemade_sports_clinic.group_portal_treatment_professional') or \
                   request.env.user.has_group('base.group_system')
            if not is_tp:
                raise AccessError(_("You don't have permission to create players."))

            # Required basics
            first_name = (post.get('first_name') or '').strip()
            last_name = (post.get('last_name') or '').strip()
            dob = (post.get('date_of_birth') or '').strip()

            if not first_name or not last_name:
                raise UserError(_('First name and last name are required'))
            if not dob:
                raise UserError(_('Date of birth is required'))

            # Validate DOB format explicitly to avoid ValueError down in ORM
            try:
                dob_date = fields.Date.to_date(dob)
            except Exception:
                values = self._prepare_portal_layout_values()
                values.update({
                    'page_name': 'add_link_player',
                    'team': team,
                    'first_name': post.get('first_name') or '',
                    'last_name': post.get('last_name') or '',
                    'date_of_birth': dob,
                    'searched': True,
                    'active_results': [],
                    'archived_results': [],
                    'is_treatment_prof': request.env.user.has_group('bemade_sports_clinic.group_portal_treatment_professional') or request.env.user.has_group('base.group_system'),
                    'states': request.env['res.country.state'].search([('country_id.code', '=', 'CA')], order='name'),
                    'countries': request.env['res.country'].search([('code', '=', 'CA')], limit=1) or request.env['res.country'].search([], order='name'),
                    'all_teams': request.env['sports.team'].search([
                        ('id', 'in', request.env['sports.team.staff'].search([
                            ('partner_id', '=', request.env.user.partner_id.id)
                        ]).mapped('team_id').ids)
                    ], order='name'),
                    'relationship_types': request.env['sports.patient.contact']._fields['contact_type'].selection,
                    'form_data': dict(post),
                    'error': _('Please enter a valid Date of Birth (YYYY-MM-DD).'),
                    'prefill_team_id': team.id,
                })
                return request.render('bemade_sports_clinic.portal_add_link_player_page', values)

            # Enforce DOB not in future and not older than 120 years
            today = fields.Date.context_today(request.env.user) or fields.Date.today()
            min_dob = today - relativedelta(years=120)
            if dob_date > today or dob_date < min_dob:
                values = self._prepare_portal_layout_values()
                values.update({
                    'page_name': 'add_link_player',
                    'team': team,
                    'first_name': post.get('first_name') or '',
                    'last_name': post.get('last_name') or '',
                    'date_of_birth': dob,
                    'searched': True,
                    'active_results': [],
                    'archived_results': [],
                    'is_treatment_prof': request.env.user.has_group('bemade_sports_clinic.group_portal_treatment_professional') or request.env.user.has_group('base.group_system'),
                    'states': request.env['res.country.state'].search([('country_id.code', '=', 'CA')], order='name'),
                    'countries': request.env['res.country'].search([('code', '=', 'CA')], limit=1) or request.env['res.country'].search([], order='name'),
                    'all_teams': request.env['sports.team'].search([
                        ('id', 'in', request.env['sports.team.staff'].search([
                            ('partner_id', '=', request.env.user.partner_id.id)
                        ]).mapped('team_id').ids)
                    ], order='name'),
                    'relationship_types': request.env['sports.patient.contact']._fields['contact_type'].selection,
                    'form_data': dict(post),
                    'error': _('Date of Birth must not be in the future and not be more than 120 years ago.'),
                    'prefill_team_id': team.id,
                })
                return request.render('bemade_sports_clinic.portal_add_link_player_page', values)

            # Build values similar to edit form, honoring permissions
            # Collect team_ids from multi-select; ensure current team is included by default
            try:
                selected_team_ids = [int(tid) for tid in request.httprequest.form.getlist('team_ids')]
            except Exception:
                selected_team_ids = []
            if not selected_team_ids:
                selected_team_ids = [team.id]
            if team.id not in selected_team_ids:
                selected_team_ids.append(team.id)
            # Restrict to teams where current user is staff (defense-in-depth against tampering)
            allowed_team_ids = request.env['sports.team.staff'].search([
                ('partner_id', '=', request.env.user.partner_id.id)
            ]).mapped('team_id').ids
            selected_team_ids = [tid for tid in selected_team_ids if tid in allowed_team_ids]
            vals = {
                'first_name': first_name,
                'last_name': last_name,
                'date_of_birth': dob,
                'team_ids': [(6, 0, list(set(selected_team_ids)))],
            }

            # Contact info
            email = (post.get('email') or '').strip()
            phone = (post.get('phone') or '').strip()
            if email:
                vals['email'] = email
            if phone:
                vals['phone'] = phone

            # Address info
            for f in ['street', 'street2', 'city', 'zip']:
                if f in post:
                    vals[f] = post.get(f) or False
            # State/Country
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

            # Extra medical/status fields (only for TP/admin)
            if is_tp:
                if 'allergies' in post:
                    vals['allergies'] = post.get('allergies') or False
                if 'team_info_notes' in post:
                    vals['team_info_notes'] = post.get('team_info_notes') or False
                if post.get('match_status'):
                    vals['match_status'] = post.get('match_status')
                if post.get('practice_status'):
                    vals['practice_status'] = post.get('practice_status')

            # Create through secured helper
            patient = request.env['sports.patient']._create_portal_patient(vals)

            # Optionally create a primary emergency contact if provided (TP/admin only)
            if is_tp:
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
                        _logger.exception('Failed to create primary emergency contact during inline player create')

            request.session['notification'] = {
                'type': 'success',
                'title': _('Player Created'),
                'message': _('%s has been created and added to the team.') % patient.name,
                'sticky': False,
            }
            # After one-step create, return to team page
            return request.redirect(f"/my/team/{team.id}")

        except (AccessError, UserError, ValidationError) as e:
            # Re-render the add/link page with preserved form values and error
            values = self._prepare_portal_layout_values()
            team = self._check_team_access(team_id)
            values.update({
                'page_name': 'add_link_player',
                'team': team,
                'first_name': post.get('first_name') or '',
                'last_name': post.get('last_name') or '',
                'date_of_birth': post.get('date_of_birth') or '',
                'searched': True,
                'active_results': [],
                'archived_results': [],
                'is_treatment_prof': request.env.user.has_group('bemade_sports_clinic.group_portal_treatment_professional') or request.env.user.has_group('base.group_system'),
                'states': request.env['res.country.state'].search([('country_id.code', '=', 'CA')], order='name'),
                'countries': request.env['res.country'].search([('code', '=', 'CA')], limit=1) or request.env['res.country'].search([], order='name'),
                'all_teams': request.env['sports.team'].search([
                    ('id', 'in', request.env['sports.team.staff'].search([
                        ('partner_id', '=', request.env.user.partner_id.id)
                    ]).mapped('team_id').ids)
                ], order='name'),
                'relationship_types': request.env['sports.patient.contact']._fields['contact_type'].selection,
                'form_data': dict(post),
                'error': str(e),
                'prefill_team_id': team.id,
            })
            return request.render('bemade_sports_clinic.portal_add_link_player_page', values)
        except Exception:
            _logger.exception('Error creating player from inline full form')
            # Render with generic error and preserved inputs
            values = self._prepare_portal_layout_values()
            team = self._check_team_access(team_id)
            values.update({
                'page_name': 'add_link_player',
                'team': team,
                'first_name': post.get('first_name') or '',
                'last_name': post.get('last_name') or '',
                'date_of_birth': post.get('date_of_birth') or '',
                'searched': True,
                'active_results': [],
                'archived_results': [],
                'is_treatment_prof': request.env.user.has_group('bemade_sports_clinic.group_portal_treatment_professional') or request.env.user.has_group('base.group_system'),
                'states': request.env['res.country.state'].search([('country_id.code', '=', 'CA')], order='name'),
                'countries': request.env['res.country'].search([('code', '=', 'CA')], limit=1) or request.env['res.country'].search([], order='name'),
                'all_teams': request.env['sports.team'].search([
                    ('id', 'in', request.env['sports.team.staff'].search([
                        ('partner_id', '=', request.env.user.partner_id.id)
                    ]).mapped('team_id').ids)
                ], order='name'),
                'relationship_types': request.env['sports.patient.contact']._fields['contact_type'].selection,
                'form_data': dict(post),
                'error': _('An unexpected error occurred.'),
                'prefill_team_id': team.id,
            })
            return request.render('bemade_sports_clinic.portal_add_link_player_page', values)

    @http.route(['/my/team/<int:team_id>/add_player/submit'],
                type='http', auth="user", website=True, methods=['POST'], csrf=True)
    def portal_add_player_submit(self, team_id, **post):
        """Handle the form submission to add a new player."""
        try:
            team = self._check_team_access(team_id)
            
            # Basic validation
            first_name = (post.get('first_name') or '').strip()
            last_name = (post.get('last_name') or '').strip()
            email = (post.get('email') or '').strip()
            phone = (post.get('phone') or '').strip()
            dob = (post.get('date_of_birth') or '').strip()
            
            if not first_name or not last_name:
                raise UserError(_("First name and last name are required"))
            # Enforce DOB for data integrity
            if not dob:
                raise UserError(_("Date of birth is required"))

            # Validate DOB format explicitly
            try:
                dob_date = fields.Date.to_date(dob)
            except Exception:
                values = {
                    'error': _('Please enter a valid Date of Birth (YYYY-MM-DD).'),
                    'team': team,
                    'page_name': 'add_player',
                }
                values.update(post)
                return request.render("bemade_sports_clinic.portal_add_player", values)

            # Enforce DOB not in future and not older than 120 years
            today = fields.Date.context_today(request.env.user) or fields.Date.today()
            min_dob = today - relativedelta(years=120)
            if dob_date > today or dob_date < min_dob:
                values = {
                    'error': _('Date of Birth must not be in the future and not be more than 120 years ago.'),
                    'team': team,
                    'page_name': 'add_player',
                }
                values.update(post)
                return request.render("bemade_sports_clinic.portal_add_player", values)
            
            # Determine if current user is allowed to set medical/status fields
            is_tp_or_admin = request.env.user.has_group('bemade_sports_clinic.group_portal_treatment_professional') or \
                             request.env.user.has_group('base.group_system')

            # Check for existing player
            existing_patient = self._find_existing_patient(
                first_name, last_name, email, phone
            )
            
            if existing_patient:
                # Determine the action taken for logging and messaging
                action_taken = []
                
                # Reactivate if archived
                if not existing_patient.active:
                    existing_patient.write({'active': True})
                    action_taken.append("reactivated")
                    _logger.debug(
                        "Reactivated archived player %s for team %s by user %s",
                        existing_patient.name, team.name, request.env.user.name
                    )
                
                # Add to team if not already a member
                if team not in existing_patient.team_ids:
                    existing_patient.write({
                        'team_ids': [(4, team.id)],
                    })
                    action_taken.append("added to team")
                    _logger.debug(
                        "Added existing player %s to team %s by user %s",
                        existing_patient.name, team.name, request.env.user.name
                    )
                
                # Determine the appropriate success message
                if "reactivated" in action_taken:
                    success_param = "player_reactivated"
                else:
                    success_param = "player_added_to_team"
                
                # Redirect to team page with appropriate message
                return request.redirect(
                    f"/my/team?team_id={team.id}&success={success_param}"
                )
            
            # No existing player found, create a new one
            patient_vals = {
                'first_name': first_name,
                'last_name': last_name,
                'team_ids': [(4, team.id)],
                'email': email or False,
                'phone': phone or False,
                'date_of_birth': dob,
            }
            # Pass through status fields if permitted
            if is_tp_or_admin:
                if post.get('match_status'):
                    patient_vals['match_status'] = post.get('match_status')
                if post.get('practice_status'):
                    patient_vals['practice_status'] = post.get('practice_status')
            
            # Create patient through the private _create_portal_patient method which has proper access controls
            patient = request.env['sports.patient']._create_portal_patient(patient_vals)
            
            # Log the action
            _logger.debug(
                "Created new player %s and added to team %s by user %s",
                patient.name, team.name, request.env.user.name
            )
            
            # Redirect to edit page with return_url back to team page for two-stage add flow
            edit_url = f"/my/player/edit?patient_id={patient.id}&return_url=/my/team/{team.id}"
            return request.redirect(edit_url)
            
        except UserError as e:
            values = {
                'error': str(e),
                'team': team,
                'page_name': 'add_player',
            }
            values.update(post)
            return request.render("bemade_sports_clinic.portal_add_player", values)
            
        except (AccessError, MissingError) as e:
            return request.redirect('/my')
            
        except Exception as e:
            _logger.exception("Error in portal_add_player_submit")
            values = {
                'error': _("An error occurred while adding the player. Please try again later."),
                'team': team,
                'page_name': 'add_player',
            }
            values.update(post)
            return request.render("bemade_sports_clinic.portal_add_player", values)

    @http.route(['/my/team/<int:team_id>/player/search'], type='json', auth="user", methods=['POST'])
    def portal_search_player(self, team_id, **post):
        """JSON endpoint to search players by name and optional date_of_birth.
        Includes archived records for treatment professionals/admins.
        """
        try:
            team = self._check_team_access(team_id)
            # Basic inputs (confidential: only name + dob)
            first_name = (post.get('first_name') or '').strip()
            last_name = (post.get('last_name') or '').strip()
            dob = (post.get('date_of_birth') or '').strip()

            if not (first_name or last_name):
                return {'ok': False, 'error': _('Provide at least a first or last name')}

            # Base domain (use ilike for partial, case-insensitive matching)
            like_first = f"%{first_name}%" if first_name else "%"
            like_last = f"%{last_name}%" if last_name else "%"
            domain = [
                ('first_name', 'ilike', like_first),
                ('last_name', 'ilike', like_last),
            ]
            if dob:
                domain.append(('date_of_birth', '=', dob))

            # Always search active first
            Patient = request.env['sports.patient']
            active_rs = Patient.search(domain + [('active', '=', True)], limit=10)

            # If user can view archived, include them too (need active_test=False)
            archived_rs = Patient.browse([])
            if request.env.user.has_group('bemade_sports_clinic.group_portal_treatment_professional') or \
               request.env.user.has_group('base.group_system'):
                archived_rs = Patient.with_context(active_test=False).search(domain + [('active', '=', False)], limit=10)

            def _to_dict(p):
                return {
                    'id': p.id,
                    'name': p.name,
                    'first_name': p.first_name,
                    'last_name': p.last_name,
                    'date_of_birth': p.date_of_birth or '',
                    'active': bool(p.active),
                    'on_team': team in p.team_ids,
                }

            return {
                'ok': True,
                'active': [_to_dict(p) for p in active_rs],
                'archived': [_to_dict(p) for p in archived_rs],
            }
        except Exception as e:
            _logger.error('Player search failed: %s', e, exc_info=True)
            return {'ok': False, 'error': _('Search failed. Please try again.')}

    @http.route(['/my/team/<int:team_id>/player/add'], type='http', auth="user", website=True, methods=['POST'], csrf=True)
    def portal_add_player_modal_submit(self, team_id, **post):
        """Handle modal submission to link existing or create a new player.
        Only treatment professionals (and admins) can directly add/link.
        Coaches must use the request route.
        """
        try:
            team = self._check_team_access(team_id)

            # Enforce role: only treatment professionals/admin can add
            if not (request.env.user.has_group('bemade_sports_clinic.group_portal_treatment_professional') or
                    request.env.user.has_group('base.group_system')):
                raise AccessError(_("You don't have permission to add players. You may submit a request instead."))

            first_name = (post.get('first_name') or '').strip()
            last_name = (post.get('last_name') or '').strip()
            dob = (post.get('date_of_birth') or '').strip()

            # Task 640: route is restricted to TPs/admins (checked above), who may
            # link ANY patient - including unteamed ones hidden by per-record ir.rules.
            # sudo() so the lookup AND the team_ids write below succeed for a patient
            # the portal user cannot yet read. Adding to a team they staff is the
            # whole point of the feature; full record access remains rule-gated.
            Patient = request.env['sports.patient'].sudo()
            existing = Patient.browse([])
            # Parse existing_id from POST if present (link flow)
            existing_id_str = post.get('existing_id')
            existing_id = int(existing_id_str) if (existing_id_str and str(existing_id_str).isdigit()) else False

            # Only require basic identity fields when creating/searching, not when linking an explicit existing_id
            if not existing_id and not (first_name or last_name):
                raise UserError(_('Provide at least a first or last name'))
            if existing_id:
                existing = Patient.with_context(active_test=False).browse(existing_id).exists()
            else:
                # Try to find existing by name + optional dob (allow partials on whichever provided)
                like_first = f"%{first_name}%" if first_name else "%"
                like_last = f"%{last_name}%" if last_name else "%"
                domain = [
                    ('first_name', 'ilike', like_first),
                    ('last_name', 'ilike', like_last),
                ]
                if dob:
                    domain.append(('date_of_birth', '=', dob))
                existing = Patient.search(domain + [('active', '=', True)], limit=1)
                if not existing:
                    existing = Patient.with_context(active_test=False).search(domain + [('active', '=', False)], limit=1)

            if existing:
                action_taken = []
                if not existing.active:
                    existing.write({'active': True})
                    action_taken.append('reactivated')
                if team not in existing.team_ids:
                    existing.write({'team_ids': [(4, team.id)]})
                    action_taken.append('added to team')

                request.session['notification'] = {
                    'type': 'success',
                    'title': _('Player Linked'),
                    'message': _('Existing player %s has been %s.') % (existing.name, ', '.join(action_taken) or _('linked')),
                    'sticky': False,
                }
                return request.redirect(f"/my/team/{team.id}")

            # Create new patient (minimal data)
            vals = {
                'first_name': first_name,
                'last_name': last_name,
                'team_ids': [(4, team.id)],
            }
            if dob:
                vals['date_of_birth'] = dob
            # Pass through status fields (route already restricts to TP/admin)
            if post.get('match_status'):
                vals['match_status'] = post.get('match_status')
            if post.get('practice_status'):
                vals['practice_status'] = post.get('practice_status')

            patient = request.env['sports.patient']._create_portal_patient(vals)

            request.session['notification'] = {
                'type': 'success',
                'title': _('Player Created'),
                'message': _('%s has been created and added to the team.') % patient.name,
                'sticky': False,
            }
            # Redirect to edit page with return_url back to team page for two-stage add flow
            edit_url = f"/my/player/edit?patient_id={patient.id}&return_url=/my/team/{team.id}"
            return request.redirect(edit_url)

        except (AccessError, UserError, ValidationError) as e:
            request.session['notification'] = {
                'type': 'danger',
                'title': _('Add Player Failed'),
                'message': str(e),
                'sticky': False,
            }
            return request.redirect(f"/my/team/{team_id}")
        except Exception as e:
            _logger.exception('Error adding player via modal')
            request.session['notification'] = {
                'type': 'danger',
                'title': _('Add Player Failed'),
                'message': _('An unexpected error occurred.'),
                'sticky': False,
            }
            return request.redirect(f"/my/team/{team_id}")

    @http.route(['/my/team/<int:team_id>/player/create'], type='http', auth='user', website=True, methods=['POST'], csrf=True)
    def portal_create_player_submit(self, team_id, **post):
        """Create a brand new player and link to team from the Add/Link page.
        Separate endpoint from link flow to simplify validation and UX.
        """
        try:
            team = self._check_team_access(team_id)

            # Only therapists/admins can create directly
            if not (request.env.user.has_group('bemade_sports_clinic.group_portal_treatment_professional') or
                    request.env.user.has_group('base.group_system')):
                raise AccessError(_("You don't have permission to create players."))

            first_name = (post.get('first_name') or '').strip()
            last_name = (post.get('last_name') or '').strip()
            dob = (post.get('date_of_birth') or '').strip()
            email = (post.get('email') or '').strip()
            phone = (post.get('phone') or '').strip()

            if not first_name or not last_name:
                raise UserError(_('First name and last name are required'))
            # Enforce DOB for data integrity
            if not dob:
                raise UserError(_('Date of birth is required'))

            vals = {
                'first_name': first_name,
                'last_name': last_name,
                'team_ids': [(4, team.id)],
                'date_of_birth': dob,
            }
            if email:
                vals['email'] = email
            if phone:
                vals['phone'] = phone
            # Pass through status fields
            if post.get('match_status'):
                vals['match_status'] = post.get('match_status')
            if post.get('practice_status'):
                vals['practice_status'] = post.get('practice_status')

            patient = request.env['sports.patient']._create_portal_patient(vals)

            request.session['notification'] = {
                'type': 'success',
                'title': _('Player Created'),
                'message': _('%s has been created and added to the team.') % patient.name,
                'sticky': False,
            }
            # Redirect to edit page with return_url back to team page for two-stage add flow
            edit_url = f"/my/player/edit?patient_id={patient.id}&return_url=/my/team/{team.id}"
            return request.redirect(edit_url)

        except (AccessError, UserError, ValidationError) as e:
            request.session['notification'] = {
                'type': 'danger',
                'title': _('Create Player Failed'),
                'message': str(e),
                'sticky': False,
            }
            return request.redirect(f"/my/team/{team_id}")
        except Exception:
            _logger.exception('Error creating player from add/link page')
            request.session['notification'] = {
                'type': 'danger',
                'title': _('Create Player Failed'),
                'message': _('An unexpected error occurred.'),
                'sticky': False,
            }
            return request.redirect(f"/my/team/{team_id}")

    @http.route(['/my/team/<int:team_id>/player/request_add'], type='http', auth='user', website=True, methods=['POST'], csrf=True)
    def portal_request_player_add(self, team_id, **post):
        """Coaches submit a request to add a player. Creates a mail.activity assigned to head therapist or fallback admin."""
        try:
            team = self._check_team_access(team_id, check_staff=True)

            # Only non-therapists need this route; therapists should use direct add
            if request.env.user.has_group('bemade_sports_clinic.group_portal_treatment_professional') or \
               request.env.user.has_group('base.group_system'):
                raise AccessError(_('You can add players directly.'))

            first_name = (post.get('first_name') or '').strip()
            last_name = (post.get('last_name') or '').strip()
            dob = (post.get('date_of_birth') or '').strip()
            reason = (post.get('reason') or '').strip()

            if not first_name or not last_name:
                raise UserError(_('First name and last name are required'))
            # Require DOB and validate format for better triage by therapists
            if not dob:
                raise UserError(_('Date of birth is required'))
            try:
                # Validate date format (YYYY-MM-DD); will raise if invalid
                fields.Date.to_date(dob)
            except Exception:
                raise UserError(_('Please enter a valid Date of Birth (YYYY-MM-DD).'))

            # Find head therapist (reuse model helper on team if available)
            # Fallback to admin if none
            head_user = False
            if hasattr(team, 'head_therapist_id') and team.head_therapist_id:
                head_user = team.head_therapist_id.user_ids[:1]
            if not head_user:
                head_user = request.env.ref('base.user_admin', raise_if_not_found=False)

            # In Odoo 18, mail.activity requires res_model_id (m2o), not res_model (char)
            # Portal users typically cannot read ir.model; use sudo safely.
            model_rec = request.env['ir.model'].sudo().search([('model', '=', 'sports.team')], limit=1)
            if not model_rec:
                raise UserError(_('Internal error: target model not found. Please contact an administrator.'))
            model_id = model_rec.id
            activity_vals = {
                'res_model_id': model_id,
                'res_id': team.id,
                'summary': _('Coach requests player addition'),
                'note': _('Requested player: %s %s%s\nReason: %s') % (
                    first_name,
                    last_name,
                    (f" (DOB: {dob})" if dob else ''),
                    (reason or _('No reason provided')),
                ),
            }
            if head_user:
                activity_vals['user_id'] = head_user.id

            # Ensure activity is created as a To Do
            todo_type = request.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
            if todo_type:
                activity_vals['activity_type_id'] = todo_type.id

            request.env['mail.activity'].sudo().create(activity_vals)

            request.session['notification'] = {
                'type': 'success',
                'title': _('Request Submitted'),
                'message': _('Your request to add a player has been sent to the head therapist.'),
                'sticky': False,
            }
            return request.redirect(f"/my/team/{team.id}")

        except (AccessError, UserError, ValidationError) as e:
            request.session['notification'] = {
                'type': 'danger',
                'title': _('Request Failed'),
                'message': str(e),
                'sticky': False,
            }
            return request.redirect(f"/my/team/{team_id}")
        except Exception as e:
            _logger.exception('Error requesting player addition')
            request.session['notification'] = {
                'type': 'danger',
                'title': _('Request Failed'),
                'message': _('An unexpected error occurred.'),
                'sticky': False,
            }
            return request.redirect(f"/my/team/{team_id}")
