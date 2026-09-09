from odoo.addons.portal.controllers.portal import CustomerPortal, pager
from odoo import http, _, fields
from odoo.tools import html2plaintext
from odoo.exceptions import UserError, AccessError
from datetime import datetime, time, timedelta
from .access_control_mixin import AccessControlMixin
import logging
import pytz
import urllib.parse

_logger = logging.getLogger(__name__)


class EventsPortal(CustomerPortal, AccessControlMixin):
    
    def _parse_portal_datetime(self, val):
        """Parse a datetime-local string coming from the portal form as a user-local
        datetime, then convert it to UTC for storage in fields.Datetime.

        Accepts formats like 'YYYY-MM-DDTHH:MM' or 'YYYY-MM-DD HH:MM' (with or without seconds).
        Returns an RFC-compliant UTC datetime string via fields.Datetime.to_string().
        """
        if not val:
            return False
        # 1) Parse to a naive datetime
        dt = None
        try:
            if 'T' in val:
                dt = datetime.strptime(val, '%Y-%m-%dT%H:%M')
            else:
                dt = datetime.strptime(val, '%Y-%m-%d %H:%M')
        except ValueError:
            try:
                if 'T' in val:
                    dt = datetime.strptime(val, '%Y-%m-%dT%H:%M:%S')
                else:
                    dt = datetime.strptime(val, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                # As a last resort, let Odoo try to coerce whatever string was provided
                return val

        # 2) Determine user's timezone
        tz_name = (http.request.context.get('tz') if http.request and http.request.context else None) or \
                  (http.request.env.user.tz if http.request else None) or 'UTC'
        try:
            user_tz = pytz.timezone(tz_name)
        except Exception:
            user_tz = pytz.UTC

        # 3) Localize and convert to UTC
        local_dt = user_tz.localize(dt)
        utc_dt = local_dt.astimezone(pytz.UTC)

        # 4) Return as proper string for fields.Datetime
        return fields.Datetime.to_string(utc_dt)
    
    def _prepare_home_portal_values(self, counters):
        """Add events count to portal home"""
        rtn = super()._prepare_home_portal_values(counters)
        if 'events_count' in counters:
            events_domain = self._prepare_events_domain()
            rtn['events_count'] = http.request.env['sports.event'].search_count(events_domain)
        return rtn

    def _prepare_events_domain(self, view_type='all'):
        """Prepare domain for sports events based on user access"""
        user = http.request.env.user
        partner = user.partner_id
        
        # Check if user is therapist (can see all events) or coach (only their teams)
        is_therapist = user.has_group('bemade_sports_clinic.group_portal_treatment_professional') or \
                      user.has_group('bemade_sports_clinic.group_sports_clinic_treatment_professional')
        is_coach = user.has_group('bemade_sports_clinic.group_portal_team_coach')
        
        if is_therapist:
            # Therapists can see all events
            base_domain = []
        elif is_coach:
            # Coaches can only see events for teams they are staff on
            team_staff_rels = partner.team_staff_rel_ids
            team_ids = team_staff_rels.mapped('team_id.id')
            base_domain = [('team_ids', 'in', team_ids or [0])]
        else:
            # No access for other users
            base_domain = [('id', '=', 0)]  # No results
        
        # Add view-specific filters
        if view_type == 'my':
            # My Events: assigned to current user
            base_domain.append(('assigned_staff_ids', 'in', [user.id]))
        elif view_type == 'unassigned':
            # Unassigned Events: no assigned staff
            base_domain.append(('assigned_staff_ids', '=', False))
        elif view_type == 'missing_timesheets':
            # Missing Timesheets:
            # Events where the current therapist (or an internal user sharing the same
            # partner) is assigned but has not submitted a timesheet yet.
            # Date constraints are handled by the standard date filters (we default
            # date_to to today in the controller).
            shared_users = http.request.env['res.users'].search([('partner_id', '=', partner.id)])
            shared_user_ids = shared_users.ids or [user.id]

            base_domain.extend([
                ('assigned_staff_ids', 'in', shared_user_ids),
                '!',
                ('timesheet_ids.user_id', 'in', shared_user_ids),
            ])
        # 'all' view uses base domain only
        
        return base_domain

    def _get_treatment_professionals(self):
        """Get all treatment professionals from team staff with relevant roles"""
        # Search for users who are on team staff with therapist, head therapist, or doctor roles
        team_staff_users = http.request.env['sports.team.staff'].search([
            ('role', 'in', ['therapist', 'head_therapist', 'doctor', 'treatment_professional'])
        ]).mapped('partner_id.user_ids')
        
        # Filter active users and sort by name
        active_users = team_staff_users.filtered(lambda u: u.active)
        
        _logger.info(f"Found {len(active_users)} treatment professionals from team staff: {[u.name for u in active_users]}")
        return active_users.sorted('name')

    def _get_accessible_teams(self):
        """Get teams accessible to current user"""
        user = http.request.env.user
        partner = user.partner_id
        
        # Check if user is therapist (can see all teams) or coach (only their teams)
        is_therapist = user.has_group('bemade_sports_clinic.group_portal_treatment_professional') or \
                      user.has_group('bemade_sports_clinic.group_sports_clinic_treatment_professional')
        
        if is_therapist:
            # Therapists can see all teams
            teams = http.request.env['sports.team'].search([])
        else:
            # Coaches can only see teams they are staff on
            team_staff_rels = partner.team_staff_rel_ids
            team_ids = team_staff_rels.mapped('team_id.id')
            teams = http.request.env['sports.team'].browse(team_ids)
        
        return teams.sorted('name')
    
    def _get_organizations(self):
        """Get organizations (parent partners of teams)"""
        teams = self._get_accessible_teams()
        organizations = teams.mapped('parent_id').filtered(lambda p: p)
        return organizations.sorted('name')

    @http.route(['/my/events', '/my/events/page/<int:page>'], type='http', auth='user', website=True)
    def view_events(self, page=1, view_type='all', team_id=None, organization_id=None, assigned_user_id=None, 
                   date_from=None, date_to=None, sortby=None, group_by=None, search=None, no_default_dates=None, **kw):
        """Main events view with filtering and pagination"""
        
        # Check access
        user = http.request.env.user
        is_therapist = user.has_group('bemade_sports_clinic.group_portal_treatment_professional') or \
                      user.has_group('bemade_sports_clinic.group_sports_clinic_treatment_professional')
        is_coach = user.has_group('bemade_sports_clinic.group_portal_team_coach')
        
        if not (is_therapist or is_coach or user.has_group('base.group_system')):
            raise AccessError(_("You don't have access to events."))
        
        # Default date filter: from today (in the *user's* timezone), matching
        # the internal "Upcoming" behavior. fields.Date.today() / datetime.today()
        # are server-local (typically UTC) and would advance the date for EDT
        # users in the late-evening / early-morning window.
        # Only apply when user did not specify any date filters AND no explicit clear flag
        # AND we are not using a view type that manages its own date constraints.
        if view_type != 'missing_timesheets' and not date_from and not date_to and not no_default_dates:
            try:
                user_tz = pytz.timezone(http.request.env.user.tz or 'UTC')
                local_today = datetime.now(pytz.utc).astimezone(user_tz).date()
                date_from = fields.Date.to_string(local_today)
            except Exception:
                # Fallback using server local date
                date_from = datetime.today().strftime('%Y-%m-%d')

        # For missing_timesheets view, avoid the default date_from=yesterday.
        # Also default the end date to today (inclusive) to match the "missing" logic.
        if view_type == 'missing_timesheets':
            no_default_dates = True
            # Only default when the parameters are truly absent.
            # If the user cleared the field, it arrives as an empty string and
            # we must not override it.
            if date_from is None and date_to is None:
                try:
                    date_to = fields.Date.to_string(fields.Date.today())
                except Exception:
                    date_to = datetime.today().strftime('%Y-%m-%d')

        # Prepare base domain
        domain = self._prepare_events_domain(view_type)
        
        # Apply additional filters
        if team_id:
            domain.append(('team_ids', 'in', [int(team_id)]))
        
        if organization_id:
            org_id = int(organization_id)
            domain.append(('partner_id', '=', org_id))
            # Debug: Log organization filter
            import logging
            _logger = logging.getLogger(__name__)
            _logger.info(f"Organization filter applied: partner_id = {org_id}")
        
        if assigned_user_id:
            domain.append(('assigned_staff_ids', 'in', [int(assigned_user_id)]))
        
        def _date_bound_to_utc(date_str, end_of_day=False):
            if not date_str:
                return None
            try:
                d = fields.Date.from_string(date_str)
            except Exception:
                return None
            tz_name = (http.request.context.get('tz') if http.request and http.request.context else None) or user.tz or 'UTC'
            try:
                user_tz = pytz.timezone(tz_name)
            except Exception:
                user_tz = pytz.UTC
            t = time.max if end_of_day else time.min
            local_dt = user_tz.localize(datetime.combine(d, t))
            utc_dt = local_dt.astimezone(pytz.UTC)
            return fields.Datetime.to_string(utc_dt)

        if date_from:
            dt_utc = _date_bound_to_utc(date_from, end_of_day=False)
            if dt_utc:
                domain.append(('date_start', '>=', dt_utc))

        if date_to:
            dt_utc = _date_bound_to_utc(date_to, end_of_day=True)
            if dt_utc:
                domain.append(('date_start', '<=', dt_utc))
        
        if search:
            domain.extend([
                '|', '|', '|',
                ('name', 'ilike', search),
                ('description', 'ilike', search),
                ('team_ids.name', 'ilike', search),
                ('venue_id.name', 'ilike', search)
            ])
        
        # Sorting options - default to date ascending as requested
        sort_options = {
            'date': 'date_start asc',
            'date_desc': 'date_start desc', 
            'name': 'name',
            'team': 'partner_id',
            'assigned': 'assigned_staff_ids',
        }
        order = sort_options.get(sortby, 'date_start asc')  # Default ascending by date
        
        # Debug: Log final domain and count
        import logging
        _logger = logging.getLogger(__name__)
        _logger.info(f"Final events domain: {domain}")
        
        # Count and pagination
        event_count = http.request.env['sports.event'].search_count(domain)
        _logger.info(f"Event count with domain: {event_count}")
        pager_values = pager(
            url='/my/events',
            url_args={'view_type': view_type, 'team_id': team_id, 'organization_id': organization_id,
                     'assigned_user_id': assigned_user_id, 'date_from': date_from,
                     'date_to': date_to, 'sortby': sortby, 'group_by': group_by, 'search': search, 'no_default_dates': no_default_dates},
            total=event_count,
            page=page,
            step=self._items_per_page,
        )
        
        # Get events
        events = http.request.env['sports.event'].search(
            domain, 
            order=order, 
            limit=self._items_per_page, 
            offset=pager_values['offset']
        )

        # Controller-level sanitation: determine which descriptions have visible text
        try:
            desc_visible = {ev.id: bool(html2plaintext(ev.description or '').strip()) for ev in events}
        except Exception:
            # Fallback: basic check
            desc_visible = {ev.id: bool((ev.description or '').strip()) for ev in events}

        # Grouping support
        grouped_events = None
        if group_by in ('team', 'month', 'week', 'therapist'):
            from collections import OrderedDict
            import unicodedata
            grouped = OrderedDict()

            def _localize(dt):
                try:
                    return fields.Datetime.context_timestamp(http.request.env.user, dt) if dt else None
                except Exception:
                    return dt

            def _slugify(text):
                # Normalize accents, lower, replace non-alnum with hyphens, collapse repeats
                if text is None:
                    text = ''
                if not isinstance(text, str):
                    text = str(text)
                norm = unicodedata.normalize('NFKD', text)
                ascii_str = ''.join([c for c in norm if not unicodedata.combining(c)])
                out = []
                prev_hyphen = False
                for ch in ascii_str.lower():
                    if ch.isalnum():
                        out.append(ch)
                        prev_hyphen = False
                    else:
                        if not prev_hyphen:
                            out.append('-')
                            prev_hyphen = True
                slug = ''.join(out).strip('-') or 'group'
                return slug

            used_dom_ids = set()

            for ev in events:
                key = None
                label = None
                if group_by == 'team':
                    primary_team = ev.team_ids[:1]
                    key = primary_team.id or 0
                    label = primary_team.name if primary_team else _('No Team')
                elif group_by == 'month':
                    ldt = _localize(ev.date_start)
                    if ldt:
                        key = f"{ldt.year}-{ldt.month:02d}"
                        label = ldt.strftime('%B %Y')
                    else:
                        key = 'no_date'
                        label = _('No Date')
                elif group_by == 'week':
                    ldt = _localize(ev.date_start)
                    if ldt:
                        iso = ldt.isocalendar()
                        key = f"{iso.year}-W{iso.week:02d}"
                        label = _('Week %(w)s, %(y)s', w=f"{iso.week:02d}", y=str(iso.year))
                    else:
                        key = 'no_date'
                        label = _('No Date')
                elif group_by == 'therapist':
                    primary = ev.assigned_staff_ids[:1]
                    key = primary.id if primary else 0
                    label = primary.name if primary else _('Unassigned')

                if key not in grouped:
                    # Construct a safe DOM id base
                    base = f"grp-{group_by}-" + (_slugify(label) if group_by in ('month', 'week') else _slugify(key))
                    dom_id = base
                    i = 1
                    while dom_id in used_dom_ids:
                        i += 1
                        dom_id = f"{base}-{i}"
                    used_dom_ids.add(dom_id)
                    grouped[key] = {'key': key, 'label': label, 'events': [], 'dom_id': dom_id}
                grouped[key]['events'].append(ev)

            grouped_events = list(grouped.values())
        
        # Get filter options
        teams = self._get_accessible_teams()
        organizations = self._get_organizations()
        treatment_professionals = self._get_treatment_professionals()
        
        # Debug: Log filter options
        _logger.info(f"Available organizations: {[(org.id, org.name) for org in organizations]}")
        _logger.info(f"Received organization_id parameter: {organization_id}")
        
        # Debug: Check sample events and their partner_id values
        sample_events = http.request.env['sports.event'].search([], limit=5)
        for event in sample_events:
            try:
                team_names = ', '.join(event.team_ids.mapped('name'))
            except Exception:
                team_names = ''
            _logger.info(f"Event '{event.name}': teams=[{team_names}], partner_id={event.partner_id.name if event.partner_id else None}")
        
        # Check if user can edit events (only therapists)
        can_edit = is_therapist
        
        values = {
            'events': events,
            'page_name': 'events',
            'pager': pager_values,
            'default_url': '/my/events',
            'return_url_encoded': urllib.parse.quote(http.request.httprequest.full_path or '/my/events', safe=''),
            'view_type': view_type,
            'team_id': int(team_id) if team_id else None,
            'organization_id': int(organization_id) if organization_id else None,
            'assigned_user_id': int(assigned_user_id) if assigned_user_id else None,
            'date_from': date_from,
            'date_to': date_to,
            'sortby': sortby,
            'group_by': group_by,
            'search': search,
            'teams': teams,
            'organizations': organizations,
            'treatment_professionals': treatment_professionals,
            'can_edit': can_edit,
            'no_default_dates': no_default_dates,
            'grouped_events': grouped_events,
            'desc_visible': desc_visible,
        }
        
        return http.request.render('bemade_sports_clinic.portal_events_list', values)

    @http.route(['/my/events/calendar'], type='http', auth='user', website=True)
    def view_events_calendar(self, **kw):
        """Calendar (month view) of accessible sports events for the user.

        Renders an HTML shell; FullCalendar in the template fetches events
        via /my/events/calendar/data.
        """
        user = http.request.env.user
        is_therapist = user.has_group('bemade_sports_clinic.group_portal_treatment_professional') or \
                      user.has_group('bemade_sports_clinic.group_sports_clinic_treatment_professional')
        is_coach = user.has_group('bemade_sports_clinic.group_portal_team_coach')
        if not (is_therapist or is_coach or user.has_group('base.group_system')):
            raise AccessError(_("You don't have access to events."))
        return http.request.render('bemade_sports_clinic.portal_events_calendar', {
            'page_name': 'events_calendar',
        })

    @http.route(['/my/events/calendar/data'], type='http', auth='user', methods=['GET'], website=True)
    def view_events_calendar_data(self, start=None, end=None, **kw):
        """JSON feed for FullCalendar.

        Returns events the current user is allowed to see (record rules
        already enforce coach team scoping; therapists see all). Honors
        the `start`/`end` ISO datetime window FullCalendar provides; if
        omitted, returns a wide rolling window. Past events are included.
        """
        import json as _json
        user = http.request.env.user
        is_therapist = user.has_group('bemade_sports_clinic.group_portal_treatment_professional') or \
                      user.has_group('bemade_sports_clinic.group_sports_clinic_treatment_professional')
        is_coach = user.has_group('bemade_sports_clinic.group_portal_team_coach')
        if not (is_therapist or is_coach or user.has_group('base.group_system')):
            return http.request.make_response('[]', headers=[('Content-Type', 'application/json')])

        domain = self._prepare_events_domain('all')
        # FullCalendar passes ISO datetimes (with or without tz). Normalize
        # to naive UTC so the comparison against Odoo's UTC-stored
        # date_start / date_end fields is correct regardless of the
        # offset the client sent.
        def _parse(dt_str):
            if not dt_str:
                return None
            try:
                if dt_str.endswith('Z'):
                    # Trailing 'Z' is valid ISO-8601 but not accepted by
                    # fromisoformat on older Pythons — drop it; the value
                    # is already UTC.
                    return datetime.fromisoformat(dt_str[:-1])
                dt = datetime.fromisoformat(dt_str)
                if dt.tzinfo is not None:
                    return dt.astimezone(pytz.UTC).replace(tzinfo=None)
                return dt
            except Exception:
                return None

        start_dt = _parse(start)
        end_dt = _parse(end)
        if start_dt is not None:
            domain.append(('date_end', '>=', fields.Datetime.to_string(start_dt)))
        if end_dt is not None:
            domain.append(('date_start', '<=', fields.Datetime.to_string(end_dt)))

        events = http.request.env['sports.event'].search(domain, limit=500)
        payload = []
        # Resolve team and assigned-user names with sudo so the popover
        # can show ALL covered teams / assigned therapists, even when
        # the current user can't directly read those records (e.g. a
        # coach seeing a co-team's therapist on a multi-team event).
        events_sudo_by_id = {ev.id: ev for ev in events.sudo()}
        for ev in events:
            ev_sudo = events_sudo_by_id.get(ev.id, ev)
            # date_start / date_end are stored as naive UTC. Emit ISO 8601
            # with an explicit UTC offset so FullCalendar localizes to the
            # browser's time zone instead of treating the wall-clock string
            # as already-local (which previously shifted every event by the
            # client's UTC offset — e.g. 11 AM EDT → 3 PM in the calendar).
            payload.append({
                'id': ev.id,
                'title': ev.name or '',
                'start': pytz.UTC.localize(ev.date_start).isoformat() if ev.date_start else None,
                'end': pytz.UTC.localize(ev.date_end).isoformat() if ev.date_end else None,
                'url': f'/my/event?event_id={ev.id}',
                'extendedProps': {
                    'teams': ev_sudo.team_ids.mapped('name'),
                    'assigned': ev_sudo.assigned_staff_ids.mapped('name'),
                    'event_type': ev.event_type or '',
                    'state': ev.state,
                },
            })
        return http.request.make_response(
            _json.dumps(payload),
            headers=[('Content-Type', 'application/json')],
        )

    @http.route(['/my/event', '/my/event/<int:event_id>'], type='http', auth='user', website=True)
    def view_event_detail(self, event_id=None, **kw):
        """View individual event detail"""
        # Canonical public URL shape is /my/event?event_id=<id> to align with
        # other portal links. The route also accepts /my/event/<int:event_id>
        # but all redirects and templates should use the query-string form.

        if not event_id:
            # If not provided in the path, try to get it from the query string
            raw_id = http.request.httprequest.args.get('event_id')
            if not raw_id:
                return http.request.redirect('/my/events')
            try:
                event_id = int(raw_id)
            except Exception:
                return http.request.redirect('/my/events')

        # Check access
        user = http.request.env.user
        is_therapist = user.has_group('bemade_sports_clinic.group_portal_treatment_professional') or \
                      user.has_group('bemade_sports_clinic.group_sports_clinic_treatment_professional')
        is_coach = user.has_group('bemade_sports_clinic.group_portal_team_coach')
        
        if not (is_therapist or is_coach or user.has_group('base.group_system')):
            raise AccessError(_("You don't have access to events."))
        
        # Get the event. If it cannot be found via the query-string based
        # entry (/my/event?event_id=..), fall back to the path-style URL so
        # existing links continue to work without a hard 404.
        event = http.request.env['sports.event'].browse(event_id)
        if not event.exists():
            return http.request.redirect(f'/my/event/{event_id}')
        
        # Check team access for coaches
        if is_coach and not is_therapist:
            partner = user.partner_id
            team_staff_rels = partner.team_staff_rel_ids
            accessible_team_ids = set(team_staff_rels.mapped('team_id.id'))
            if not event.team_ids or not (set(event.team_ids.ids) & accessible_team_ids):
                raise AccessError(_("You don't have access to this event."))
        
        # Check if user can edit (only therapists)
        can_edit = is_therapist
        
        # Helper to format dt for datetime-local inputs in user's tz
        def _format_dt_local(dt):
            if not dt:
                return ''
            try:
                tz_name = (http.request.context.get('tz') if http.request and http.request.context else None) or \
                          (http.request.env.user.tz if http.request else None) or 'UTC'
                user_tz = pytz.timezone(tz_name)
            except Exception:
                user_tz = pytz.UTC
            # Odoo stores as UTC-naive; localize to UTC first
            if dt.tzinfo is None:
                utc_dt = pytz.UTC.localize(dt)
            else:
                utc_dt = dt.astimezone(pytz.UTC)
            local_dt = utc_dt.astimezone(user_tz)
            return local_dt.strftime('%Y-%m-%dT%H:%M')

        # Timesheet context for current user — TPs only. Coaches don't
        # have read access to sports.event.timesheet, so we skip every
        # timesheet read for them and the template hides the tab.
        my_ts = http.request.env['sports.event.timesheet']
        has_my_timesheet = False
        local_dt_map = {}
        missing_users = http.request.env['res.users']
        missing_count = 0
        missing_names = ''
        if is_therapist or user.has_group('base.group_system'):
            my_ts = http.request.env['sports.event.timesheet'].search([
                ('event_id', '=', event.id),
                ('user_id', '=', user.id),
            ], order='id desc', limit=1)
            has_my_timesheet = bool(my_ts)
            try:
                my_timesheets = event.timesheet_ids.filtered(lambda t: t.user_id.id == user.id)
                for ts in my_timesheets:
                    local_dt_map[ts.id] = {
                        'travel_start': _format_dt_local(ts.travel_start),
                        'coverage_start': _format_dt_local(ts.coverage_start),
                        'coverage_end': _format_dt_local(ts.coverage_end),
                        'travel_end': _format_dt_local(ts.travel_end),
                    }
            except Exception:
                local_dt_map = {}
            missing_users = event._get_missing_timesheet_user_ids() if hasattr(event, '_get_missing_timesheet_user_ids') else http.request.env['res.users']
            missing_count = len(missing_users)
            missing_names = ', '.join(missing_users.mapped('name')) if missing_users else ''

        # Optional return URL (to preserve filtered events list context)
        return_url = http.request.httprequest.args.get('return_url')
        if return_url and isinstance(return_url, str) and return_url.startswith('%2F'):
            try:
                return_url = urllib.parse.unquote(return_url)
            except Exception:
                pass
        if return_url and isinstance(return_url, str) and '&amp;' in return_url:
            return_url = return_url.replace('&amp;', '&')
        if return_url:
            # Only allow returning to the portal events list (prevent open redirects)
            if not return_url.startswith('/my/events'):
                return_url = None
        else:
            # Fallback: infer from referrer (e.g. user navigated via /my/event/<id>)
            # Only accept referrers that point to /my/events to avoid open redirects.
            try:
                ref = http.request.httprequest.referrer
                if ref:
                    parsed = urllib.parse.urlparse(ref)
                    candidate = parsed.path
                    if parsed.query:
                        candidate = f"{candidate}?{parsed.query}"
                    if candidate.startswith('/my/events'):
                        return_url = candidate
            except Exception:
                return_url = None

        _logger.debug("[EventsPortal] view_event_detail event_id=%s return_url=%s", event.id if event else event_id, return_url)

        event_return_url = f"/my/event/{event.id}"
        if return_url:
            try:
                event_return_url = event_return_url + "?return_url=%s" % urllib.parse.quote(return_url, safe='')
            except Exception:
                event_return_url = event_return_url

        # Timesheets are TP-only — coaches don't have read access to
        # sports.event.timesheet, so even iterating raises AccessError.
        # The template hides the tab and content when this is False.
        can_view_timesheets = is_therapist or user.has_group('base.group_system')
        # Sudo recordset so display-only fields (team names, assigned
        # therapists) render fully even when a coach can't read every
        # team on a multi-team event.
        event_sudo = event.sudo()
        values = {
            'event': event,
            'event_sudo': event_sudo,
            'page_name': 'event_detail',
            'can_edit': can_edit,
            'can_view_timesheets': can_view_timesheets,
            'return_url': return_url,
            'event_return_url': event_return_url,
            'timesheet_local_dt': local_dt_map,
            # Timesheet UI context
            'has_my_timesheet': has_my_timesheet,
            'my_timesheet': my_ts,
            # Default local times for modal fields (fallback to therapist/event range)
            'ts_travel_start_local': _format_dt_local(my_ts.travel_start if my_ts else (event.therapist_start or event.date_start)),
            'ts_coverage_start_local': _format_dt_local(my_ts.coverage_start if my_ts else (event.therapist_start or event.date_start)),
            'ts_coverage_end_local': _format_dt_local(my_ts.coverage_end if my_ts else (event.therapist_end or event.date_end)),
            'ts_travel_end_local': _format_dt_local(my_ts.travel_end if my_ts else (event.therapist_end or event.date_end)),
            # Completion warnings
            'missing_count': missing_count,
            'missing_names': missing_names,
        }
        
        return http.request.render('bemade_sports_clinic.portal_event_detail', values)

    def _get_event_return_qs(self, post):
        return_url = post.get('return_url') if post else None
        if return_url and isinstance(return_url, str) and return_url.startswith('%2F'):
            try:
                return_url = urllib.parse.unquote(return_url)
            except Exception:
                pass
        if return_url and isinstance(return_url, str) and '&amp;' in return_url:
            return_url = return_url.replace('&amp;', '&')
        if not return_url:
            try:
                ref = http.request.httprequest.referrer
                if ref:
                    parsed = urllib.parse.urlparse(ref)
                    qs = urllib.parse.parse_qs(parsed.query or '')
                    if qs.get('return_url'):
                        return_url = qs.get('return_url')[0]
            except Exception:
                return_url = None

        if return_url and isinstance(return_url, str) and '&amp;' in return_url:
            return_url = return_url.replace('&amp;', '&')

        if return_url and not str(return_url).startswith('/my/events'):
            return_url = None

        return ('&return_url=%s' % urllib.parse.quote(return_url, safe='')) if return_url else ''

    @http.route(['/my/event/<int:event_id>/timesheet/add'], type='http', auth='user', website=True, methods=['POST'], csrf=False)
    def add_timesheet(self, event_id, **post):
        """Create a new timesheet for the current user for the event"""
        user = http.request.env.user
        # Access: therapists only for adding timesheets (or system)
        is_therapist = user.has_group('bemade_sports_clinic.group_portal_treatment_professional') or \
                      user.has_group('bemade_sports_clinic.group_sports_clinic_treatment_professional')
        if not (is_therapist or user.has_group('base.group_system')):
            raise AccessError(_("You don't have permission to add timesheets."))

        event = http.request.env['sports.event'].browse(event_id)
        if not event.exists():
            return http.request.not_found()

        return_qs = self._get_event_return_qs(post)
        _logger.debug(
            "[EventsPortal] add_timesheet event_id=%s post.return_url=%s return_qs=%s referrer=%s",
            event.id,
            post.get('return_url'),
            return_qs,
            http.request.httprequest.referrer,
        )

        # Build values
        vals = {
            'event_id': event.id,
            'user_id': user.id,
        }
        for key, field_name in [('travel_start', 'travel_start'),
                                ('coverage_start', 'coverage_start'),
                                ('coverage_end', 'coverage_end'),
                                ('travel_end', 'travel_end')]:
            if post.get(key):
                vals[field_name] = self._parse_portal_datetime(post.get(key))

        # If clinic event, disallow travel time: travel must equal coverage bounds
        try:
            if event.event_type == 'clinic':
                # Parse to datetime for comparison
                ts_travel_start = fields.Datetime.from_string(vals.get('travel_start')) if vals.get('travel_start') else None
                ts_cov_start = fields.Datetime.from_string(vals.get('coverage_start')) if vals.get('coverage_start') else None
                ts_travel_end = fields.Datetime.from_string(vals.get('travel_end')) if vals.get('travel_end') else None
                ts_cov_end = fields.Datetime.from_string(vals.get('coverage_end')) if vals.get('coverage_end') else None

                # If coverage provided, ensure travel equals coverage; otherwise we allow create to default them equal
                if ts_cov_start and ts_travel_start and ts_travel_start != ts_cov_start:
                    return http.request.redirect(
                        f"/my/event/{event.id}?ts_error="
                        + urllib.parse.quote(_("Clinic events cannot include travel time. Travel Start must equal Coverage Start."))
                        + return_qs
                    )
                if ts_cov_end and ts_travel_end and ts_travel_end != ts_cov_end:
                    return http.request.redirect(
                        f"/my/event/{event.id}?ts_error="
                        + urllib.parse.quote(_("Clinic events cannot include travel time. Travel End must equal Coverage End."))
                        + return_qs
                    )
        except Exception:
            # Non-blocking: fall through to model validations if any
            pass

        ts_model = http.request.env['sports.event.timesheet']
        try:
            ts = ts_model.create(vals)
            ts_id = ts.id
            target = f'/my/event/{event.id}?ts_saved=1{return_qs}'
            _logger.debug("[EventsPortal] add_timesheet redirect=%s", target)
            return http.request.redirect(target)
        except Exception as e:
            msg = str(e).replace('\n', ' ').replace('\r', ' ')
            return http.request.redirect(f'/my/event/{event.id}?ts_error={urllib.parse.quote(msg)}{return_qs}')

    @http.route(['/my/event/<int:event_id>/cancel'], type='http', auth='user', website=True, methods=['POST'], csrf=False)
    def cancel_event(self, event_id, **post):
        user = http.request.env.user
        is_therapist = user.has_group('bemade_sports_clinic.group_portal_treatment_professional') or \
                      user.has_group('bemade_sports_clinic.group_sports_clinic_treatment_professional')
        if not (is_therapist or user.has_group('base.group_system')):
            raise AccessError(_("You don't have permission to cancel events."))

        event = http.request.env['sports.event'].browse(event_id)
        if not event.exists():
            return http.request.not_found()

        return_qs = self._get_event_return_qs(post)
        reason = (post.get('cancel_reason') or '').strip()
        if not reason:
            return http.request.redirect(
                f"/my/event/{event.id}?error=" + urllib.parse.quote(_("Please provide a cancellation reason.")) + return_qs
            )

        try:
            event.with_context(portal_cancel_event=True).write({'state': 'cancelled'})
            try:
                event.message_post(body=_('Event cancelled via portal. Reason: %s') % reason)
            except Exception:
                pass
            return http.request.redirect(f'/my/event/{event.id}?cancelled=1{return_qs}')
        except Exception as e:
            msg = str(e).replace('\n', ' ').replace('\r', ' ')
            return http.request.redirect(f'/my/event/{event.id}?error={urllib.parse.quote(msg)}{return_qs}')

    @http.route(['/my/event/<int:event_id>/edit'], type='http', auth='user', website=True)
    def edit_event_form(self, event_id, **kw):
        """Edit event form - only accessible to therapists"""
        
        # Check access - only therapists can edit
        user = http.request.env.user
        is_therapist = user.has_group('bemade_sports_clinic.group_portal_treatment_professional') or \
                      user.has_group('bemade_sports_clinic.group_sports_clinic_treatment_professional')
        
        if not (is_therapist or user.has_group('base.group_system')):
            raise AccessError(_("You don't have permission to edit events."))
        
        # Get the event
        event = http.request.env['sports.event'].browse(event_id)
        if not event.exists():
            return http.request.not_found()

        return_url = kw.get('return_url')
        if return_url and isinstance(return_url, str) and '&amp;' in return_url:
            return_url = return_url.replace('&amp;', '&')
        if return_url and not return_url.startswith('/my/events'):
            return_url = None
        if not return_url:
            try:
                ref = http.request.httprequest.referrer
                if ref:
                    parsed = urllib.parse.urlparse(ref)
                    qs = urllib.parse.parse_qs(parsed.query or '')
                    cand = (qs.get('return_url') or [None])[0]
                    if cand and isinstance(cand, str) and '&amp;' in cand:
                        cand = cand.replace('&amp;', '&')
                    if cand and cand.startswith('/my/events'):
                        return_url = cand
            except Exception:
                return_url = None
        
        # Get filter options for form
        teams = http.request.env['sports.team'].search([])
        organizations = teams.mapped('parent_id').filtered(lambda p: p).sorted('name')
        treatment_professionals = self._get_treatment_professionals()
        venues = http.request.env['res.partner'].search([('is_venue', '=', True)])

        # Helper to format dt for datetime-local inputs in user's tz
        def _format_dt_local(dt):
            if not dt:
                return ''
            try:
                tz_name = (http.request.context.get('tz') if http.request and http.request.context else None) or \
                          (http.request.env.user.tz if http.request else None) or 'UTC'
                user_tz = pytz.timezone(tz_name)
            except Exception:
                user_tz = pytz.UTC
            # Odoo stores as UTC-naive; localize to UTC first
            if dt.tzinfo is None:
                utc_dt = pytz.UTC.localize(dt)
            else:
                utc_dt = dt.astimezone(pytz.UTC)
            local_dt = utc_dt.astimezone(user_tz)
            return local_dt.strftime('%Y-%m-%dT%H:%M')

        values = {
            'event': event,
            'teams': teams,
            'organizations': organizations,
            'treatment_professionals': treatment_professionals,
            'venues': venues,
            'page_name': 'event_edit',
            'return_url': return_url,
            # Preformatted local datetime values
            'date_start_local': _format_dt_local(event.date_start),
            'date_end_local': _format_dt_local(event.date_end),
            'therapist_start_local': _format_dt_local(event.therapist_start),
            'therapist_end_local': _format_dt_local(event.therapist_end),
            'organization_id_selected': event.partner_id.id if event.partner_id else None,
        }

        return http.request.render('bemade_sports_clinic.portal_event_edit', values)

    @http.route(['/my/event/<int:event_id>/save'], type='http', auth='user', website=True, methods=['POST'], csrf=False)
    def save_event(self, event_id, **post):
        """Save event changes - only accessible to therapists"""
        
        # Debug: Log all POST data
        _logger.info(f"Full POST data received: {dict(post)}")
        _logger.info(f"POST keys: {list(post.keys())}")
        
        # Check access - only therapists can edit
        user = http.request.env.user
        is_therapist = user.has_group('bemade_sports_clinic.group_portal_treatment_professional') or \
                      user.has_group('bemade_sports_clinic.group_sports_clinic_treatment_professional')
        
        if not (is_therapist or user.has_group('base.group_system')):
            raise AccessError(_("You don't have permission to edit events."))
        
        # Get the event
        event = http.request.env['sports.event'].browse(event_id)
        if not event.exists():
            return http.request.not_found()

        return_qs = self._get_event_return_qs(post)
        
        try:
            # Update event fields
            update_vals = {}
            
            if 'name' in post:
                update_vals['name'] = post['name']
            if 'description' in post:
                update_vals['description'] = post['description']
            # Teams: accept team_ids (list or CSV) or legacy team_id
            team_ids_param = post.get('team_ids') or post.get('team_ids[]')
            if team_ids_param is not None:
                if isinstance(team_ids_param, list):
                    team_ids_list = [int(x) for x in team_ids_param if x]
                else:
                    team_ids_list = [int(x.strip()) for x in str(team_ids_param).split(',') if x.strip()]
                update_vals['team_ids'] = [(6, 0, team_ids_list)]
            elif 'team_id' in post and post['team_id']:
                update_vals['team_ids'] = [(6, 0, [int(post['team_id'])])]
            if 'venue_id' in post and post['venue_id']:
                update_vals['venue_id'] = int(post['venue_id'])
            if 'event_type' in post:
                update_vals['event_type'] = post['event_type']
            # NOTE: Workflow is internal-only for now. Do not accept 'state' from portal.
            # TODO(bemade_sports_clinic): Implement therapist portal actions to change state
            # (e.g., mark in progress, mark completed) with proper access checks.
            if 'date_start' in post and post['date_start']:
                update_vals['date_start'] = self._parse_portal_datetime(post['date_start'])
                    
            if 'date_end' in post and post['date_end']:
                update_vals['date_end'] = self._parse_portal_datetime(post['date_end'])
                    
            if 'therapist_start' in post and post['therapist_start']:
                update_vals['therapist_start'] = self._parse_portal_datetime(post['therapist_start'])
                    
            if 'therapist_end' in post and post['therapist_end']:
                update_vals['therapist_end'] = self._parse_portal_datetime(post['therapist_end'])
            
            # Handle assigned staff (many2many)
            # Check for both array-style and regular parameter names
            staff_param = None
            if 'assigned_staff_ids' in post:
                staff_param = post['assigned_staff_ids']
                param_name = 'assigned_staff_ids'
            elif 'assigned_staff_ids[]' in post:
                staff_param = post['assigned_staff_ids[]']
                param_name = 'assigned_staff_ids[]'
            
            if staff_param is not None:
                _logger.info(f"Raw {param_name} from form: {staff_param} (type: {type(staff_param)})")
                staff_ids = []
                if isinstance(staff_param, list):
                    # Handle list of values
                    staff_ids = [int(x) for x in staff_param if x]
                elif staff_param:
                    # Handle single value or comma-separated string
                    if ',' in str(staff_param):
                        # Comma-separated values from JavaScript workaround
                        staff_ids = [int(x.strip()) for x in str(staff_param).split(',') if x.strip()]
                    else:
                        # Single value
                        staff_ids = [int(staff_param)]
                _logger.info(f"Processed staff_ids: {staff_ids}")
                update_vals['assigned_staff_ids'] = [(6, 0, staff_ids)]
            else:
                _logger.info("No assigned_staff_ids parameter in post data")
                # If no staff selected, clear the field
                update_vals['assigned_staff_ids'] = [(6, 0, [])]
            
            # Update the event
            event.write(update_vals)

            return http.request.redirect(f'/my/event/{event_id}?success=1{return_qs}')
            
        except Exception as e:
            # Clean error message to prevent redirect issues with newlines
            error_msg = str(e).replace('\n', ' ').replace('\r', ' ')
            return http.request.redirect(f'/my/event/{event_id}/edit?error={urllib.parse.quote(error_msg)}{return_qs}')

    @http.route(['/my/event/create'], type='http', auth='user', website=True)
    def create_event_form(self, **kw):
        """Display event creation form - only accessible to therapists"""
        # Access: only therapists (or system) can create
        user = http.request.env.user
        is_therapist = user.has_group('bemade_sports_clinic.group_portal_treatment_professional') or \
                      user.has_group('bemade_sports_clinic.group_sports_clinic_treatment_professional')
        if not (is_therapist or user.has_group('base.group_system')):
            raise AccessError(_("You don't have permission to create events."))

        # Options for form
        teams = self._get_accessible_teams() if not user.has_group('base.group_system') else http.request.env['sports.team'].search([])
        organizations = teams.mapped('parent_id').filtered(lambda p: p).sorted('name')
        treatment_professionals = self._get_treatment_professionals()
        venues = http.request.env['res.partner'].search([('is_venue', '=', True)])

        values = {
            'teams': teams,
            'organizations': organizations,
            'treatment_professionals': treatment_professionals,
            'venues': venues,
            'page_name': 'event_create',
        }
        return http.request.render('bemade_sports_clinic.portal_event_create', values)

    @http.route(['/my/event/create/submit'], type='http', auth='user', website=True, methods=['POST'], csrf=False)
    def create_event_submit(self, **post):
        """Handle event creation - only accessible to therapists"""
        # Access: only therapists (or system) can create
        user = http.request.env.user
        is_therapist = user.has_group('bemade_sports_clinic.group_portal_treatment_professional') or \
                      user.has_group('bemade_sports_clinic.group_sports_clinic_treatment_professional')
        if not (is_therapist or user.has_group('base.group_system')):
            raise AccessError(_("You don't have permission to create events."))

        try:
            create_vals = {}

            # Required fields
            if 'name' in post and post['name']:
                create_vals['name'] = post['name']
            else:
                raise UserError(_('Event name is required.'))

            # Teams: accept team_ids (list or CSV) or legacy team_id
            team_ids_param = post.get('team_ids') or post.get('team_ids[]')
            team_ids_list = []
            if team_ids_param is not None:
                if isinstance(team_ids_param, list):
                    team_ids_list = [int(x) for x in team_ids_param if x]
                else:
                    team_ids_list = [int(x.strip()) for x in str(team_ids_param).split(',') if x.strip()]
            elif post.get('team_id'):
                team_ids_list = [int(post['team_id'])]
            if not team_ids_list:
                raise UserError(_('At least one team is required.'))
            create_vals['team_ids'] = [(6, 0, team_ids_list)]

            # Optional simple fields
            if 'description' in post:
                create_vals['description'] = post['description']
            if 'venue_id' in post and post['venue_id']:
                create_vals['venue_id'] = int(post['venue_id'])
            if 'event_type' in post:
                create_vals['event_type'] = post['event_type']
            # NOTE: Workflow is internal-only for now. Do not accept 'state' from portal.
            # TODO(bemade_sports_clinic): Implement therapist portal actions to change state
            # (e.g., mark in progress, mark completed) with proper access checks.

            # Datetime fields
            def _parse_dt(val):
                return self._parse_portal_datetime(val)

            if 'date_start' in post and post['date_start']:
                create_vals['date_start'] = _parse_dt(post['date_start'])
            else:
                raise UserError(_('Event start time is required.'))

            if 'date_end' in post and post['date_end']:
                create_vals['date_end'] = _parse_dt(post['date_end'])
            else:
                raise UserError(_('Event end time is required.'))

            # Default therapist times to event times if not provided
            if post.get('therapist_start'):
                create_vals['therapist_start'] = _parse_dt(post['therapist_start'])
            else:
                create_vals['therapist_start'] = create_vals['date_start']

            if post.get('therapist_end'):
                create_vals['therapist_end'] = _parse_dt(post['therapist_end'])
            else:
                create_vals['therapist_end'] = create_vals['date_end']

            # Assigned staff (same handling as save_event)
            staff_param = None
            if 'assigned_staff_ids' in post:
                staff_param = post['assigned_staff_ids']
            elif 'assigned_staff_ids[]' in post:
                staff_param = post['assigned_staff_ids[]']

            staff_ids = []
            if staff_param is not None:
                _logger.info(f"Raw assigned_staff_ids from form: {staff_param} (type: {type(staff_param)})")
                if isinstance(staff_param, list):
                    staff_ids = [int(x) for x in staff_param if x]
                elif staff_param:
                    if ',' in str(staff_param):
                        staff_ids = [int(x.strip()) for x in str(staff_param).split(',') if x.strip()]
                    else:
                        staff_ids = [int(staff_param)]
            create_vals['assigned_staff_ids'] = [(6, 0, staff_ids)]

            create_vals['state'] = 'confirmed'

            # Task creation is handled by the model's create() default logic

            event = http.request.env['sports.event'].create(create_vals)

            return http.request.redirect(f'/my/event/{event.id}?created=1')

        except Exception as e:
            # Preserve user input and re-render the create form with errors
            error_msg = str(e).replace('\n', ' ').replace('\r', ' ')

            # Options for form
            user = http.request.env.user
            teams = self._get_accessible_teams() if not user.has_group('base.group_system') else http.request.env['sports.team'].search([])
            organizations = teams.mapped('parent_id').filtered(lambda p: p).sorted('name')
            treatment_professionals = self._get_treatment_professionals()
            venues = http.request.env['res.partner'].search([('is_venue', '=', True)])

            # Assigned staff selected
            staff_param = post.get('assigned_staff_ids') or post.get('assigned_staff_ids[]')
            assigned_staff_selected = []
            if staff_param is not None:
                if isinstance(staff_param, list):
                    assigned_staff_selected = [int(x) for x in staff_param if x]
                elif staff_param:
                    if ',' in str(staff_param):
                        assigned_staff_selected = [int(x.strip()) for x in str(staff_param).split(',') if x.strip()]
                    else:
                        try:
                            assigned_staff_selected = [int(staff_param)]
                        except Exception:
                            assigned_staff_selected = []

            values = {
                'teams': teams,
                'organizations': organizations,
                'treatment_professionals': treatment_professionals,
                'venues': venues,
                'page_name': 'event_create',
                'error': error_msg,
                # Preserve simple fields
                'name': post.get('name') or '',
                'event_type': post.get('event_type') or '',
                'state': 'confirmed',
                'team_ids_selected': team_ids_list,
                'venue_id_selected': int(post['venue_id']) if post.get('venue_id') else None,
                'description_html': post.get('description') or '',
                # Preserve datetime-local fields as entered (local strings)
                'date_start_local': post.get('date_start') or '',
                'date_end_local': post.get('date_end') or '',
                'therapist_start_local': post.get('therapist_start') or '',
                'therapist_end_local': post.get('therapist_end') or '',
                # Preserve assigned staff selections
                'assigned_staff_selected': assigned_staff_selected,
                'organization_id_selected': int(post['organization_id']) if post.get('organization_id') else None,
            }
            return http.request.render('bemade_sports_clinic.portal_event_create', values)

    @http.route(['/my/venue/create'], type='json', auth='user', website=True, methods=['POST'], csrf=False)
    def create_venue_ajax(self, **post):
        """Create a venue partner record via AJAX for portal users.
        Uses surgical sudo to avoid ACL/record rule issues, but restricts fields strictly.
        """
        user = http.request.env.user
        is_therapist = user.has_group('bemade_sports_clinic.group_portal_treatment_professional') or \
                      user.has_group('bemade_sports_clinic.group_sports_clinic_treatment_professional')
        if not (is_therapist or user.has_group('base.group_system')):
            return {'success': False, 'error': _("You don't have permission to create venues.")}

        name = (post.get('name') or '').strip()
        if not name:
            return {'success': False, 'error': _('Venue name is required.')}

        try:
            vals = {
                'name': name,
                'is_company': True,
                'is_venue': True,
                'type': 'other',
            }
            # Optional address fields
            for key in ['street', 'street2', 'city', 'zip']:
                if post.get(key):
                    vals[key] = post.get(key)

            # Optional country/state by id
            if post.get('country_id'):
                try:
                    vals['country_id'] = int(post.get('country_id'))
                except Exception:
                    pass
            if post.get('state_id'):
                try:
                    vals['state_id'] = int(post.get('state_id'))
                except Exception:
                    pass

            venue = http.request.env['res.partner'].sudo().create(vals)
            return {'success': True, 'id': venue.id, 'name': venue.name}
        except Exception as e:
            return {'success': False, 'error': str(e)}
