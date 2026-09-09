import logging
import base64
import io
import re
import unicodedata
from odoo import http, fields, _
from odoo.exceptions import UserError, ValidationError
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager
from .access_control_mixin import AccessControlMixin
from datetime import datetime

_logger = logging.getLogger(__name__)


class PatientInjuryPortal(CustomerPortal, AccessControlMixin):
    """Controller for all injury reporting functionality in the portal"""
    
    # Access control methods now inherited from AccessControlMixin
    
    @http.route(['/my/patient/injury/new'], type='http', auth='user', website=True)
    def create_injury_form(self, patient_id=None, **post):
        """Show form to create a new injury report"""
        if not patient_id:
            return request.redirect('/my/players')
            
        try:
            patient = self._check_access_to_patient(patient_id)
        except UserError as e:
            return request.render('http_routing.http_error', {
                'status_code': 403, 
                'status_message': 'Forbidden',
                'error_message': str(e)
            })
            
        # Resolve team context. Read the patient's teams via sudo so
        # multi-team players still render the "which team is this injury
        # for?" picker even when one of the teams is outside the user's
        # tightened TP/coach scope.
        patient_teams = patient.sudo().team_ids
        # Accept team context from both kwargs and request.params (GET)
        team_id_param = post.get('team_id') or request.params.get('team_id')
        selected_team_id = None
        team_context_id = None
        if team_id_param:
            try:
                team_id_int = int(team_id_param)
            except Exception:
                team_id_int = None
            if team_id_int and team_id_int in patient_teams.ids:
                # Explicit, validated team context coming from navigation
                selected_team_id = team_id_int
                team_context_id = team_id_int
        # Single-team inference for form convenience only (no breadcrumb context)
        if not selected_team_id and len(patient_teams) == 1:
            selected_team_id = patient_teams[0].id
        require_team_selection = len(patient_teams) > 1 and not selected_team_id
        team = None
        if team_context_id:
            # sudo so an out-of-scope team still renders by name in the form
            team = request.env['sports.team'].sudo().browse(team_context_id)
        
        # Compute default return_url based on explicit team navigation context only
        return_url = post.get('return_url') or request.params.get('return_url')
        if not return_url:
            if team_context_id:
                return_url = f'/my/player?player_id={patient_id}&team_id={team_context_id}'
            else:
                return_url = f'/my/player?player_id={patient_id}'

        # Check if user is a treatment professional
        # Use request.env.user.has_group() directly to avoid security violations
        is_treatment_prof = request.env.user.has_group('bemade_sports_clinic.group_portal_treatment_professional')
        user = request.env.user
        
        # Get treatment professionals for the multi-select field (if treatment professional)
        treatment_professionals = []
        parental_consent_options = None
        if is_treatment_prof:
            # Include both portal and internal treatment professionals
            portal_tp_group = request.env.ref('bemade_sports_clinic.group_portal_treatment_professional')
            internal_tp_group = request.env.ref('bemade_sports_clinic.group_sports_clinic_treatment_professional')
            treatment_professionals = request.env['res.users'].search([
                ('groups_id', 'in', [portal_tp_group.id, internal_tp_group.id])
            ])
            parental_consent_options = request.env['sports.patient.injury']._fields['parental_consent'].selection
        
        values = {
            'patient': patient,
            'return_url': return_url,
            'page_name': 'report_injury',
            'is_treatment_prof': is_treatment_prof,  # Pass flag to template for conditional display
            'treatment_professionals': treatment_professionals,
            'parental_consent_options': parental_consent_options,
            'patient_teams': patient_teams,
            'selected_team_id': selected_team_id,
            'require_team_selection': require_team_selection,
            'team': team,
            'team_context_id': team_context_id,
            'error': post.get('error'),
        }
        
        return request.render('bemade_sports_clinic.portal_create_injury', values)
    
    @http.route(['/my/patient/injury/create'], type='http', auth='user', website=True, methods=['POST'])
    def create_injury_submit(self, **post):
        """Process the form submission to create a new injury"""
        patient_id = post.get('patient_id')
        
        if not patient_id:
            return request.redirect('/my/players')
            
        try:
            patient = self._check_access_to_patient(patient_id)
        except UserError as e:
            return request.render('http_routing.http_error', {
                'status_code': 403, 
                'status_message': 'Forbidden',
                'error_message': str(e)
            })
            
        # Resolve team from submission or context. sudo so that
        # multi-team players whose teams the user can't all read still
        # validate the submitted team properly.
        patient_teams = patient.sudo().team_ids
        submitted_team = post.get('team_id')
        team_id = None
        if submitted_team:
            try:
                submitted_team_int = int(submitted_team)
            except Exception:
                submitted_team_int = None
            if submitted_team_int and submitted_team_int in patient_teams.ids:
                team_id = submitted_team_int
            else:
                # Invalid team submitted; re-render form with error
                return request.redirect(f"/my/patient/injury/new?patient_id={patient.id}&error=invalid_team")
        else:
            if len(patient_teams) == 1:
                team_id = patient_teams[0].id
            elif len(patient_teams) > 1:
                # Team selection required when multiple teams and no selection provided
                return request.redirect(f"/my/patient/injury/new?patient_id={patient.id}&error=team_required")
            
        # Check if the current user is a treatment professional
        is_treatment_prof = request.env.user.has_group('bemade_sports_clinic.group_portal_treatment_professional')
        
        # Prepare values for injury creation
        vals = {
            'patient_id': patient.id,
            'diagnosis': post.get('diagnosis', ''),
            'external_notes': post.get('external_notes', ''),
        }
        
        # Handle injury date and injury_date_na checkbox
        if post.get('injury_date_na'):
            vals['injury_date_na'] = True
            vals['injury_date'] = False  # Clear injury_date if N/A is checked
        elif post.get('injury_date'):
            vals['injury_date'] = post.get('injury_date')
            vals['injury_date_na'] = False
        
        # Add team_id if resolved
        if team_id:
            vals['team_id'] = int(team_id)
        
        # Handle optional fields
        if post.get('parental_consent'):
            vals['parental_consent'] = post.get('parental_consent')
        
        if post.get('predicted_resolution_date'):
            vals['predicted_resolution_date'] = post.get('predicted_resolution_date')
            
        # Handle internal notes for treatment professionals
        if is_treatment_prof and post.get('internal_notes'):
            vals['internal_notes'] = post.get('internal_notes')

        # Hidden-from-coaches flag (TPs only — checkbox)
        if is_treatment_prof:
            vals['hidden_from_coaches'] = bool(post.get('hidden_from_coaches'))
            
        # Create the injury record - portal users now have create permission
        # Determine role flags to choose safe context
        is_internal_user = request.env.user.has_group('base.group_user')
        is_tp_internal = request.env.user.has_group('bemade_sports_clinic.group_sports_clinic_treatment_professional')
        is_tp_portal = request.env.user.has_group('bemade_sports_clinic.group_portal_treatment_professional')
        suppress_notifications = not (is_internal_user or is_tp_internal or is_tp_portal)

        env_injury = request.env['sports.patient.injury']
        if suppress_notifications:
            env_injury = env_injury.with_context(mail_notrack=True, mail_create_nolog=True, mail_create_nosubscribe=True)
        injury = env_injury.create(vals)
        
        # Determine role for assignment behavior
        # Use request.env.user.has_group() directly to avoid security violations
        is_portal_coach = request.env.user.has_group('bemade_sports_clinic.group_portal_team_coach')
        is_treatment_prof = request.env.user.has_group('bemade_sports_clinic.group_portal_treatment_professional')
        user = request.env.user

        # Assignment rules:
        # - If any therapists were explicitly selected in the form, assign exactly those and do not auto-assign others.
        # - If none were selected, auto-assign team therapists (if determinable) and do not auto-assign the creator by default.

        # Read explicit selections (checkbox-based multi-select)
        selected_tp_ids = []
        if is_treatment_prof:
            selected_tp_ids = request.httprequest.form.getlist('treatment_professional_ids[]') or []
            # Normalize to ints and remove empties
            selected_tp_ids = [int(tp_id) for tp_id in selected_tp_ids if tp_id]

        if selected_tp_ids:
            # Respect explicit selection only
            if suppress_notifications:
                injury.with_context(mail_notrack=True, mail_create_nolog=True, mail_create_nosubscribe=True).write({'treatment_professional_ids': [(6, 0, selected_tp_ids)]})
            else:
                injury.write({'treatment_professional_ids': [(6, 0, selected_tp_ids)]})
        else:
            # No explicit selection: perform team-based auto-assignment (if a single team context exists)
            if team_id:
                selected_team_id = int(team_id)
                # Find therapists (head and regular) specifically for this team
                team_staff = request.env['sports.team.staff'].sudo().search([
                    ('team_id', '=', selected_team_id),
                    ('role', 'in', ['head_therapist', 'therapist'])
                ])

                # Collect user IDs from team staff (prefer direct user_ids relation, fallback to partner mapping)
                team_tp_user_ids = set()
                for staff in team_staff:
                    if staff.user_ids:
                        for u in staff.user_ids:
                            team_tp_user_ids.add(u.id)
                    else:
                        users = request.env['res.users'].sudo().search([('partner_id', '=', staff.partner_id.id)])
                        for u in users:
                            team_tp_user_ids.add(u.id)

                if user.id in team_tp_user_ids and (user.id not in (selected_tp_ids or [])):
                    # Do not auto-assign the creating user unless explicitly selected
                    team_tp_user_ids.discard(user.id)

                if not team_tp_user_ids:
                    _logger.warning("No valid therapists found to assign to the injury for team %s", selected_team_id)

                if team_tp_user_ids:
                    if suppress_notifications:
                        injury.with_context(mail_notrack=True, mail_create_nolog=True, mail_create_nosubscribe=True).write({'treatment_professional_ids': [(6, 0, list(team_tp_user_ids))]})
                    else:
                        injury.write({'treatment_professional_ids': [(6, 0, list(team_tp_user_ids))]})
            else:
                _logger.info(
                    "Skipping team-based therapist auto-assignment: patient %s has %s teams",
                    patient.id,
                    len(patient.team_ids),
                )
            
        # Handle treatment note creation if provided by treatment professional
        if is_treatment_prof and post.get('treatment_note'):
            treatment_note_text = post.get('treatment_note').strip()
            if treatment_note_text:
                try:
                    # Create treatment note using the controller helper to ensure correct permissions and linkage
                    self._add_treatment_note(injury.patient_id, treatment_note_text, injury)
                    _logger.info(f"Treatment note added to injury {injury.id} by user {request.env.user.id}")
                except Exception as e:
                    _logger.error(f"Failed to create treatment note for injury {injury.id}: {str(e)}")
        
        # Trigger recomputation of patient status based on the injury
        patient._compute_is_injured()
        patient._compute_stage()
        
        # Use explicit navigation context (team_context_id) for redirect, not inferred team assignment
        team_context_id = post.get('team_context_id')
        try:
            team_context_id_int = int(team_context_id) if team_context_id else None
        except Exception:
            team_context_id_int = None

        if team_context_id_int and team_context_id_int in patient_teams.ids:
            return_url = f'/my/player?player_id={patient_id}&team_id={team_context_id_int}'
        else:
            return_url = f'/my/player?player_id={patient_id}'
        values = {
            'return_url': return_url,
        }
        
        return request.render('bemade_sports_clinic.portal_injury_created', values)
        
    # _check_access_to_injury method now inherited from AccessControlMixin

    def _sanitize_filename(self, name):
        """Return an ASCII-safe filename for HTTP headers/storage.
        - Normalize unicode
        - Remove path separators
        - Strip non-ASCII characters
        - Replace illegal chars with underscore
        - Truncate to a reasonable length
        """
        try:
            if not name:
                return 'document'
            # Normalize unicode then drop accents
            norm = unicodedata.normalize('NFKD', str(name))
            norm = norm.replace('/', '-').replace('\\', '-')
            # Encode to ASCII, ignore non-ASCII
            ascii_name = norm.encode('ascii', 'ignore').decode('ascii')
            # Allow alnum, space, dot, dash, underscore only
            ascii_name = re.sub(r'[^A-Za-z0-9._ -]', '_', ascii_name)
            # Collapse whitespace and trim
            ascii_name = re.sub(r'\s+', ' ', ascii_name).strip()
            if not ascii_name:
                ascii_name = 'document'
            # Limit length
            return ascii_name[:150]
        except Exception:
            return 'document'
        
    @http.route(['/my/injury/edit'], type='http', auth='user', website=True)
    def edit_injury_form(self, injury_id=None, team_id=None, **post):
        """Show form to edit an existing injury"""
        if not injury_id:
            return request.redirect('/my/players')
            
        try:
            injury = self._check_access_to_injury(injury_id)
        except UserError as e:
            return request.render('http_routing.http_error', {
                'status_code': 403, 
                'status_message': 'Forbidden',
                'error_message': str(e)
            })

        # Determine return URL. If an explicit return_url is provided, respect it;
        # otherwise, build a player URL, optionally including validated team context
        # so that saving/cancelling from a team-aware player page keeps team_id.
        return_url = post.get('return_url')
        team = None
        team_context_id = None

        if not return_url:
            team_param = team_id or request.params.get('team_id')
            if team_param:
                try:
                    # Best-effort team validation for navigation context
                    team_rec = self._check_team_access(team_param, check_staff=True)
                    if team_rec:
                        team = team_rec
                        team_context_id = team_rec.id
                except UserError:
                    team = None
                    team_context_id = None

            if team_context_id:
                return_url = f'/my/player?player_id={injury.patient_id.id}&team_id={team_context_id}'
            else:
                return_url = f'/my/player?player_id={injury.patient_id.id}'
        
        # Get possible injury stages - treatment professionals can change stage
        stages = []
        # Use request.env.user.has_group() directly to avoid security violations
        is_treatment_prof = request.env.user.has_group('bemade_sports_clinic.group_portal_treatment_professional')
        user = request.env.user
        
        if is_treatment_prof:
            stage_selection = request.env['sports.patient.injury']._fields['stage'].selection
            stages = [(k, v) for k, v in stage_selection]
        
        # Get treatment professionals for the multi-select field (both portal and internal)
        portal_tp_group = request.env.ref('bemade_sports_clinic.group_portal_treatment_professional')
        internal_tp_group = request.env.ref('bemade_sports_clinic.group_sports_clinic_treatment_professional')
        treatment_professionals = request.env['res.users'].search([
            ('groups_id', 'in', [portal_tp_group.id, internal_tp_group.id])
        ])
        
        # Get parental consent options if treatment professional
        parental_consent_options = None
        if is_treatment_prof:
            parental_consent_options = request.env['sports.patient.injury']._fields['parental_consent'].selection
            
        values = {
            'injury': injury,
            'stages': stages,
            'treatment_professionals': treatment_professionals,
            'parental_consent_options': parental_consent_options,
            'return_url': return_url,
            'is_treatment_prof': is_treatment_prof,
            'page_name': 'edit_injury',
            'error': post.get('error'),
            'success': post.get('success'),
            'team': team,
            'team_context_id': team_context_id,
        }
        
        return request.render('bemade_sports_clinic.portal_edit_injury', values)
        
    @http.route(['/my/injury/save'], type='http', auth='user', website=True, methods=['POST'])
    def edit_injury_submit(self, **post):
        """Process the form submission to update an injury"""
        injury_id = post.get('injury_id')
        
        if not injury_id:
            return request.redirect('/my/players')
            
        try:
            injury = self._check_access_to_injury(injury_id)
        except UserError as e:
            return request.render('http_routing.http_error', {
                'status_code': 403, 
                'status_message': 'Forbidden',
                'error_message': str(e)
            })
            
        # Get user's role
        # Use request.env.user.has_group() directly to avoid security violations
        is_treatment_prof = request.env.user.has_group('bemade_sports_clinic.group_portal_treatment_professional')
        user = request.env.user
        
        # Prepare values for injury update
        vals = {}
        
        # Fields everyone can update
        vals.update({
            'diagnosis': post.get('diagnosis', injury.diagnosis or ''),
            'external_notes': post.get('external_notes', injury.external_notes or ''),
        })
        
        # Handle injury date and N/A checkbox
        if post.get('injury_date_na'):
            vals['injury_date_na'] = True
            vals['injury_date'] = False  # Clear the date if N/A is checked
        else:
            vals['injury_date_na'] = False
            if post.get('injury_date'):
                vals['injury_date'] = post.get('injury_date')
        

        
        # Handle resolution dates
        if post.get('predicted_resolution_date'):
            vals['predicted_resolution_date'] = post.get('predicted_resolution_date')
        
        if post.get('resolution_date'):
            vals['resolution_date'] = post.get('resolution_date')
        
        # Handle treatment professionals (checkbox-based multi-select)
        selected_tp_ids = request.httprequest.form.getlist('treatment_professional_ids[]')
        if selected_tp_ids:
            # Convert to integers and set using Odoo's many2many syntax
            prof_ids = [int(pid) for pid in selected_tp_ids if pid]
            vals['treatment_professional_ids'] = [(6, 0, prof_ids)]
        else:
            # If no checkboxes are selected, clear the treatment professionals
            vals['treatment_professional_ids'] = [(6, 0, [])]
        
        # Fields only treatment professionals can update
        if is_treatment_prof:
            if post.get('internal_notes'):
                vals['internal_notes'] = post.get('internal_notes')

            if post.get('stage'):
                vals['stage'] = post.get('stage')

            if post.get('parental_consent'):
                vals['parental_consent'] = post.get('parental_consent')

            # Checkbox: present in form ⇒ True, absent ⇒ False
            vals['hidden_from_coaches'] = bool(post.get('hidden_from_coaches'))
                
        # Update the injury
        injury.sudo().write(vals)
        
        # Add a treatment note if provided
        if post.get('treatment_note') and is_treatment_prof:
            # Add treatment note for injury
            self._add_treatment_note(injury.patient_id, post.get('treatment_note'), injury)
        
        # Redirect back to the edit form with success message
        return_url = post.get('return_url', f'/my/injury/edit?injury_id={injury_id}')
        return request.redirect(f'{return_url}&success=injury_updated')
        
    def _add_treatment_note(self, patient, note_content, injury=None):
        """Helper method to add a treatment note to a patient, optionally linked to an injury"""
        if not note_content.strip():
            return False
        
        # Validate patient parameter
            
        # Create a new treatment note linked to patient, optionally to injury
        vals = {
            'patient_id': patient.id,
            'note': note_content,
            'date': fields.Date.today(),
            'user_id': request.env.user.id,
        }
        # Create treatment note with prepared values
        
        # If injury is provided, link the note to it
        if injury:
            vals['injury_id'] = injury.id
            
        request.env['sports.treatment.note'].sudo().create(vals)
        
        return True
        
    @http.route(['/my/patient/notes'], type='http', auth='user', website=True)
    def view_treatment_notes(self, patient_id=None, team_id=None, **post):
        """View treatment notes for a patient (patient-centric only).

        If an optional team_id is provided, the template can render
        team-aware breadcrumbs (Teams → Team → Player → Treatment Notes).
        """
        if not patient_id:
            return request.redirect('/my/players')

        # Get user's role
        is_treatment_prof = request.env.user.has_group('bemade_sports_clinic.group_portal_treatment_professional')

        # Patient context only: show all notes for this patient, with optional
        # injury links rendered in the template
        try:
            patient = self._check_access_to_patient(patient_id)
        except UserError as e:
            return request.render('http_routing.http_error', {
                'status_code': 403,
                'status_message': 'Forbidden',
                'error_message': str(e),
            })

        notes = request.env['sports.treatment.note'].sudo().search(
            [('patient_id', '=', int(patient_id))],
            order='date desc, id desc',
        )

        team = None
        team_context_id = None
        if team_id:
            # Best-effort team resolution; access is still governed by
            # patient access checks above and portal record rules.
            team = request.env['sports.team'].browse(int(team_id))
            if team.exists() and team in patient.team_ids:
                team_context_id = team.id
            else:
                team = None

        values = {
            'injury': None,
            'notes': notes,
            'patient': patient,
            'team': team,
            'team_context_id': team_context_id,
            'is_treatment_prof': is_treatment_prof,
            'page_name': 'patient_notes',
            'error': post.get('error'),
            'success': post.get('success'),
        }
        
        return request.render('bemade_sports_clinic.portal_treatment_notes', values)
        
    @http.route(['/my/injury/note/add'], type='http', auth='user', website=True, methods=['POST'])
    def add_treatment_note(self, **post):
        """Add a new treatment note to a patient, optionally linked to an injury.

        Honors an optional `return_url` form field so the caller (e.g.
        the new Notes tab on the player page) can redirect back to its
        origin instead of the standalone notes page.
        """
        injury_id = post.get('injury_id')
        patient_id = post.get('patient_id')
        return_url = post.get('return_url')

        if not injury_id and not patient_id:
            return request.redirect('/my/players')

        def _redirect(qs):
            target = return_url or f'/my/patient/notes?patient_id={patient_id or ""}'
            # Insert qs before any URL fragment so the #notes anchor
            # (or any other anchor) survives the redirect.
            base, frag = (target.split('#', 1) + [''])[:2]
            sep = '&' if '?' in base else '?'
            tail = f"#{frag}" if frag else ''
            return request.redirect(f"{base}{sep}{qs}{tail}")

        is_treatment_prof = request.env.user.has_group('bemade_sports_clinic.group_portal_treatment_professional')
        if not is_treatment_prof:
            return _redirect('error=permission_denied')

        note_content = post.get('note')
        if not note_content or not note_content.strip():
            return _redirect('error=empty_note')

        if injury_id:
            try:
                injury = self._check_access_to_injury(injury_id)
                patient = injury.patient_id
                self._add_treatment_note(patient, note_content, injury)
                return _redirect('success=note_added')
            except UserError as e:
                return request.render('http_routing.http_error', {
                    'status_code': 403,
                    'status_message': 'Forbidden',
                    'error_message': str(e),
                })

        try:
            patient = self._check_access_to_patient(patient_id)
        except UserError as e:
            return request.render('http_routing.http_error', {
                'status_code': 403,
                'status_message': 'Forbidden',
                'error_message': str(e),
            })
        self._add_treatment_note(patient, note_content)
        return _redirect('success=note_added')
        
    @http.route(['/my/injury/documents'], type='http', auth='user', website=True)
    def view_injury_documents(self, injury_id=None, team_id=None, **post):
        """View documents attached to an injury.

        When an optional ``team_id`` is provided (e.g. coming from a
        team-context player page), this is used purely for navigation
        and breadcrumb context (Teams → Team → Player → Injury → Documents).
        Access is still governed entirely by injury access checks and
        record rules.
        """
        if not injury_id:
            return request.redirect('/my/players')
            
        try:
            injury = self._check_access_to_injury(injury_id)
        except UserError as e:
            return request.render('http_routing.http_error', {
                'status_code': 403, 
                'status_message': 'Forbidden',
                'error_message': str(e)
            })
            
        # Get documents for this injury
        documents = request.env['sports.injury.document'].sudo().search(
            [('injury_id', '=', int(injury_id))],
            order='create_date desc'
        )
        
        # Get user's role
        is_treatment_prof = request.env.user.has_group('bemade_sports_clinic.group_portal_treatment_professional')

        # Optional team navigation context for breadcrumbs
        team = None
        team_context_id = None
        if team_id:
            try:
                team_rec = request.env['sports.team'].browse(int(team_id))
                if team_rec.exists():
                    team = team_rec
                    team_context_id = team_rec.id
            except Exception:
                team = None
                team_context_id = None
        
        # Document categories (aligned with model)
        categories = [
            ('medical', 'Medical'),
            ('medical_imaging', 'Medical Imaging'),
            ('prescription', 'Prescription'),
            ('other', 'Other'),
        ]
        
        values = {
            'injury': injury,
            'documents': documents,
            'patient': injury.patient_id,
            'is_treatment_prof': is_treatment_prof,
            'page_name': 'injury_documents',
            'error': post.get('error'),
            'success': post.get('success'),
            'categories': categories,
            'team': team,
            'team_context_id': team_context_id,
        }
        
        return request.render('bemade_sports_clinic.portal_injury_documents', values)
        
    @http.route(['/my/injury/document/upload'], type='http', auth='user', website=True, methods=['POST'])
    def upload_injury_document(self, **post):
        """Upload a document for an injury"""
        injury_id = post.get('injury_id')
        
        if not injury_id:
            return request.redirect('/my/players')
            
        try:
            injury = self._check_access_to_injury(injury_id)
        except UserError as e:
            return request.render('http_routing.http_error', {
                'status_code': 403, 
                'status_message': 'Forbidden',
                'error_message': str(e)
            })
            
        # Check if file was uploaded
        attachment = post.get('attachment')
        if not attachment:
            return request.redirect(f'/my/injury/documents?injury_id={injury_id}&error=no_file')
            
        # Process the file
        try:
            name = attachment.filename
            safe_file_name = self._sanitize_filename(name)
            file_content = attachment.read()
            file_size = len(file_content)
            
            # Check file size (limit to 10MB)
            if file_size > 10 * 1024 * 1024:  # 10MB in bytes
                return request.redirect(f'/my/injury/documents?injury_id={injury_id}&error=file_too_large')
                
            # Create the document
            document = request.env['sports.injury.document'].sudo().create({
                'injury_id': int(injury_id),
                'patient_id': injury.patient_id.id,
                'name': post.get('document_name', name),
                'description': post.get('description', ''),
                'category': post.get('category', 'other'),
                'file_content': base64.b64encode(file_content),
                'file_name': safe_file_name,
                'created_by_id': request.env.user.id,
            })
            
            # Redirect back to documents page with success message
            return request.redirect(f'/my/injury/documents?injury_id={injury_id}&success=document_uploaded')
            
        except Exception as e:
            _logger.error(f"Error uploading document: {e}")
            return request.redirect(f'/my/injury/documents?injury_id={injury_id}&error=upload_failed')
            
    @http.route(['/my/injury/document/download/<int:document_id>'], type='http', auth='user')
    def download_injury_document(self, document_id, **post):
        """Download a document attached to an injury"""
        document = request.env['sports.injury.document'].sudo().browse(int(document_id))
        
        if not document.exists():
            raise request.not_found()
            
        try:
            # Prefer checking access via injury; if no injury, check via patient
            if document.injury_id:
                self._check_access_to_injury(document.injury_id.id)
            else:
                self._check_access_to_patient(document.patient_id.id)
        except UserError:
            raise request.not_found()
        
        # Return the file for download
        safe_name = self._sanitize_filename(document.file_name)
        return request.make_response(
            base64.b64decode(document.file_content),
            headers=[
                ('Content-Type', 'application/octet-stream'),
                ('Content-Disposition', f'attachment; filename="{safe_name}"'),
            ]
        )

    @http.route(['/my/patient/document/download/<int:document_id>'], type='http', auth='user')
    def download_patient_document(self, document_id, **post):
        """Download a document linked to a patient (injury optional)."""
        document = request.env['sports.injury.document'].sudo().browse(int(document_id))
        if not document.exists():
            raise request.not_found()
        try:
            # Access check based on patient (primary link)
            self._check_access_to_patient(document.patient_id.id)
        except UserError:
            raise request.not_found()
        safe_name = self._sanitize_filename(document.file_name)
        return request.make_response(
            base64.b64decode(document.file_content),
            headers=[
                ('Content-Type', 'application/octet-stream'),
                ('Content-Disposition', f'attachment; filename="{safe_name}"'),
            ]
        )

    @http.route(['/my/patient/document/upload'], type='http', auth='user', website=True, methods=['POST'])
    def upload_patient_document(self, **post):
        """Upload a document directly to a patient (injury optional)."""
        patient_id = post.get('patient_id')
        if not patient_id:
            return request.redirect('/my/players')

        try:
            patient = self._check_access_to_patient(patient_id)
        except UserError as e:
            return request.render('http_routing.http_error', {
                'status_code': 403,
                'status_message': 'Forbidden',
                'error_message': str(e)
            })

        return_url = post.get('return_url') or f'/my/player?player_id={patient.id}#documents'

        def _redirect(qs):
            # Insert qs before any URL fragment so the anchor survives.
            base, frag = (return_url.split('#', 1) + [''])[:2]
            sep = '&' if '?' in base else '?'
            tail = f"#{frag}" if frag else ''
            return request.redirect(f"{base}{sep}{qs}{tail}")

        attachment = post.get('attachment')
        if not attachment:
            return _redirect('error=no_file')

        try:
            name = attachment.filename
            safe_file_name = self._sanitize_filename(name)
            file_content = attachment.read()
            file_size = len(file_content)

            # 10MB limit
            if file_size > 10 * 1024 * 1024:
                return _redirect('error=file_too_large')

            # Create patient-linked document (injury optional)
            request.env['sports.injury.document'].sudo().create({
                'patient_id': patient.id,
                'injury_id': int(post['injury_id']) if post.get('injury_id') else False,
                'name': post.get('document_name', name),
                'description': post.get('description', ''),
                'category': post.get('category', 'other'),
                'file_content': base64.b64encode(file_content),
                'file_name': safe_file_name,
                'created_by_id': request.env.user.id,
            })

            return _redirect('success=document_uploaded')

        except Exception as e:
            _logger.error(f"Error uploading patient document: {e}")
            return _redirect('error=upload_failed')
        
    @http.route(['/my/injury/document/delete/<int:document_id>'], type='http', auth='user', website=True)
    def delete_injury_document(self, document_id, **post):
        """Delete a document attached to an injury"""
        document = request.env['sports.injury.document'].sudo().browse(int(document_id))
        
        if not document.exists():
            raise request.not_found()
            
        try:
            # Check access to the injury this document belongs to
            injury = self._check_access_to_injury(document.injury_id.id)
        except UserError:
            raise request.not_found()
            
        # Check if user is a treatment professional (only they can delete documents)
        is_treatment_prof = request.env.user.has_group('bemade_sports_clinic.group_portal_treatment_professional')
        if not is_treatment_prof:
            return request.redirect(f'/my/injury/documents?injury_id={document.injury_id.id}&error=permission_denied')
            
        # Delete the document
        injury_id = document.injury_id.id
        document.sudo().unlink()
        
        # Redirect back to documents page with success message
        return request.redirect(f'/my/injury/documents?injury_id={injury_id}&success=document_deleted')
        
    @http.route(['/my/injury/verify'], type='http', auth='user', website=True, methods=['POST'])
    def verify_injury(self, injury_id, **post):
        """Verify an injury (change status from unverified to active)"""
        # Only treatment professionals / admins may verify injuries...
        if not (request.env.user.has_group('bemade_sports_clinic.group_portal_treatment_professional') or
                request.env.user.has_group('base.group_system')):
            return request.redirect('/my')

        # ...and only for an injury on a team they staff. Task 640 follow-up: the
        # role check alone let a TP verify ANY injury by id (per-record access was
        # never enforced). _check_access_to_injury raises UserError when the user
        # has no team overlap with the injury's patient (or it doesn't exist).
        try:
            injury = self._check_access_to_injury(injury_id)
        except UserError:
            return request.redirect('/my')

        try:
            injury.action_verify_injury()
            return request.redirect(f'/my/player?player_id={injury.patient_id.id}')
        except Exception as e:
            _logger.error(f"Error verifying injury: {e}")
            return request.redirect('/my')
            
    @http.route(['/my/injury/delete'], type='http', auth='user', website=True, methods=['POST'])
    def delete_injury(self, **post):
        """Delete an injury record (only for treatment professionals)"""
        injury_id = post.get('injury_id')
        return_url = post.get('return_url', '/my/players')
        
        if not injury_id:
            return request.redirect(return_url)
            
        try:
            injury = self._check_access_to_injury(injury_id)
        except UserError as e:
            return request.render('http_routing.http_error', {
                'status_code': 403, 
                'status_message': 'Forbidden',
                'error_message': str(e)
            })
            
        # Check if user is a treatment professional (only they can delete injuries)
        is_treatment_prof = request.env.user.has_group('bemade_sports_clinic.group_portal_treatment_professional')
        if not is_treatment_prof:
            return request.redirect(f'{return_url}?error=permission_denied')
            
        # Get patient info before deletion for redirect
        patient_id = injury.patient_id.id
        
        try:
            # Delete the injury record (this will cascade delete related records)
            injury.sudo().unlink()
            _logger.info(f"Injury {injury_id} deleted by user {request.env.user.id}")
            
            # Redirect back to player page with success message
            return request.redirect(f'/my/player?player_id={patient_id}&success=injury_deleted')
            
        except Exception as e:
            _logger.error(f"Error deleting injury {injury_id}: {str(e)}")
            return request.redirect(f'{return_url}?error=delete_failed')
