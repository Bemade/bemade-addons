from odoo import api, fields, models
from odoo.exceptions import ValidationError


class SportsEvent(models.Model):
    _name = 'sports.event'
    _description = 'Sports Event'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_start asc, name'
    _rec_name = 'name'

    # Portal access group definition - only authorized portal users
    _portal_groups = 'base.group_user,bemade_sports_clinic.group_portal_treatment_professional,bemade_sports_clinic.group_portal_team_coach'

    # ========================================
    # CORE EVENT FIELDS (Portal Accessible)
    # ========================================
    
    name = fields.Char(
        string='Event Name',
        required=True,
        tracking=True,
        groups=_portal_groups,
        help='Name of the sports event'
    )
    
    description = fields.Html(
        string='Description',
        groups=_portal_groups,
        help='Detailed description of the event'
    )
    
    # Event timing
    date_start = fields.Datetime(
        string='Event Start Time',
        required=True,
        tracking=True,
        index=True,
        groups=_portal_groups,
        default=fields.Datetime.now,
        help='When the event starts'
    )
    
    date_end = fields.Datetime(
        string='Event End Time',
        required=True,
        tracking=True,
        index=True,
        groups=_portal_groups,
        help='When the event ends'
    )
    
    # Therapist coverage timing (independent fields that sync with task)
    therapist_start = fields.Datetime(
        string='Therapist Start Time',
        tracking=True,
        index=True,
        groups=_portal_groups,
        help='When therapist coverage begins (may be before event start for preparation)'
    )
    
    therapist_end = fields.Datetime(
        string='Therapist End Time',
        tracking=True,
        index=True,
        groups=_portal_groups,
        help='When therapist coverage ends (may be after event end for cleanup)'
    )
    
    # Event details
    venue_id = fields.Many2one(
        'res.partner',
        string='Venue',
        domain=[('is_venue', '=', True)],
        groups=_portal_groups,
        help='Venue/location where the event takes place'
    )
    
    event_type = fields.Selection([
        ('game', 'Game'),
        ('practice', 'Practice'),
        ('training', 'Training'),
        ('meeting', 'Team Meeting'),
        ('clinic', 'Clinic'),
        ('other', 'Other')
    ], string='Event Type', default='game', groups=_portal_groups, tracking=True)
    
    # Status and priority
    state = fields.Selection([
        ('confirmed', 'Confirmed'),
        ('to_invoice', 'To Invoice'),
        ('invoiced', 'Invoiced'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='confirmed', tracking=True, groups=_portal_groups)
    
    # ========================================
    # RELATIONSHIPS (Portal Accessible)
    # ========================================
    
    team_ids = fields.Many2many(
        'sports.team',
        'sports_event_team_rel',
        'event_id',
        'team_id',
        string='Teams',
        required=True,
        tracking=True,
        groups=_portal_groups,
        help='The sports teams this event involves'
    )
    
    # Staff assignments
    assigned_staff_ids = fields.Many2many(
        'res.users',
        'sports_event_staff_rel',
        'event_id',
        'user_id',
        string='Assigned Staff',
        groups=_portal_groups,
        help='Treatment professionals assigned to this event'
    )

    # Timesheets: one per assigned therapist
    timesheet_ids = fields.One2many(
        'sports.event.timesheet', 'event_id',
        string='Timesheets',
        help='Timesheets logged by assigned therapists for this event'
    )

    timesheet_count = fields.Integer(
        string='Timesheet Count',
        compute='_compute_timesheet_count',
        store=False,
        help='Number of timesheets recorded for this event'
    )

    activity_count = fields.Integer(
        string='Activity Count',
        compute='_compute_activity_count'
    )
    
    # ========================================
    # COMPUTED FIELDS
    # ========================================
    
    partner_id = fields.Many2one(
        'res.partner',
        string='Organization',
        compute='_compute_partner_id',
        store=True,
        groups=_portal_groups,
        help='Parent organization (computed from teams)'
    )
    
    duration = fields.Float(
        string='Event Duration (Hours)',
        compute='_compute_duration',
        store=True,
        groups=_portal_groups,
        help='Event duration in hours'
    )
    
    therapist_duration = fields.Float(
        string='Therapist Coverage Duration (Hours)',
        compute='_compute_therapist_duration',
        store=True,
        groups=_portal_groups,
        help='Therapist coverage duration in hours'
    )

    # Billing readiness flags
    has_uninvoiced_timesheets = fields.Boolean(
        string='Has Uninvoiced Timesheets',
        compute='_compute_has_uninvoiced_timesheets',
        store=False,
        help='True when any timesheet still needs customer invoicing (coverage or travel)'
    )
    
    is_today = fields.Boolean(
        string='Is Today',
        compute='_compute_is_today',
        help='Whether the event is happening today'
    )
    
    is_upcoming = fields.Boolean(
        string='Is Upcoming',
        compute='_compute_is_upcoming',
        help='Whether the event is in the future'
    )

    # Helper field used in views to filter staff pickers to treatment professionals only
    treatment_professional_user_ids = fields.Many2many(
        'res.users',
        string='Treatment Professional Users',
        compute='_compute_treatment_professional_user_ids',
        store=False,
        help='All users who are treatment professionals (internal and portal). Used to filter staff selection.'
    )
    
    # ========================================
    # COMPUTED METHODS
    # ========================================
    
    @api.depends('team_ids', 'team_ids.parent_id')
    def _compute_partner_id(self):
        """Compute partner/organization from teams.

        Enforce that all selected teams share the same parent organization.
        """
        for event in self:
            if not event.team_ids:
                event.partner_id = False
                continue
            orgs = event.team_ids.mapped('parent_id').filtered(lambda p: p)
            if not orgs:
                event.partner_id = False
            else:
                unique_orgs = orgs.mapped('id')
                if len(set(unique_orgs)) > 1:
                    # Defer raising until constraints; here choose the first to keep compute stable
                    event.partner_id = orgs[0]
                else:
                    event.partner_id = orgs[0]
    
    def action_recompute_partner_ids(self):
        """Recompute partner_id for all events (for fixing organization filter)"""
        all_events = self.search([])
        all_events._compute_partner_id()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': f'Recomputed partner_id for {len(all_events)} events',
                'type': 'success',
            }
        }
    
    @api.depends('date_start', 'date_end')
    def _compute_duration(self):
        """Calculate event duration in hours"""
        for event in self:
            if event.date_start and event.date_end:
                delta = event.date_end - event.date_start
                event.duration = delta.total_seconds() / 3600.0
            else:
                event.duration = 0.0
    
    @api.depends('therapist_start', 'therapist_end')
    def _compute_therapist_duration(self):
        """Calculate therapist coverage duration in hours"""
        for event in self:
            if event.therapist_start and event.therapist_end:
                delta = event.therapist_end - event.therapist_start
                event.therapist_duration = delta.total_seconds() / 3600.0
            else:
                event.therapist_duration = 0.0

    def _compute_has_uninvoiced_timesheets(self):
        for event in self:
            ts = event.timesheet_ids
            event.has_uninvoiced_timesheets = any(t.customer_ready_to_invoice for t in ts)
    
    @api.depends('date_start')
    def _compute_is_today(self):
        """Check if event is today"""
        from datetime import date
        today = date.today()
        for event in self:
            if event.date_start:
                event.is_today = event.date_start.date() == today
            else:
                event.is_today = False
    
    @api.depends('date_start')
    def _compute_is_upcoming(self):
        """Check if event is in the future"""
        from datetime import datetime
        now = datetime.now()
        for event in self:
            if event.date_start:
                event.is_upcoming = event.date_start > now
            else:
                event.is_upcoming = False

    def _compute_treatment_professional_user_ids(self):
        """Compute the list of users who are treatment professionals.

        Includes both internal treatment professionals and portal treatment professionals.
        """
        # Resolve groups safely via env.ref
        tp_internal = self.env.ref('bemade_sports_clinic.group_sports_clinic_treatment_professional', raise_if_not_found=False)
        tp_portal = self.env.ref('bemade_sports_clinic.group_portal_treatment_professional', raise_if_not_found=False)
        group_ids = [g.id for g in (tp_internal, tp_portal) if g]

        users = self.env['res.users']
        if group_ids:
            users = users.search([('active', '=', True), ('groups_id', 'in', group_ids)])
        else:
            users = users.browse()

        for event in self:
            event.treatment_professional_user_ids = users

    def _compute_timesheet_count(self):
        for event in self:
            event.timesheet_count = len(event.timesheet_ids)

    def _compute_activity_count(self):
        for event in self:
            event.activity_count = self.env['mail.activity'].search_count([
                ('res_model', '=', 'sports.event'),
                ('res_id', '=', event.id)
            ])
    
    # ========================================
    # ONCHANGE METHODS
    # ========================================
    
    @api.onchange('date_start')
    def _onchange_date_start(self):
        """When event start changes:
        - therapist_start defaults to same as date_start if not already set
        - date_end defaults to +2 hours only if not already set or invalid
        - therapist_end defaults to date_end if not already set
        """
        if self.date_start:
            from datetime import timedelta
            # Respect existing values (e.g., provided from calendar selection)
            if not self.therapist_start:
                self.therapist_start = self.date_start
            # If no date_end or it's earlier/equal to start, set sensible default
            if not self.date_end or self.date_end <= self.date_start:
                self.date_end = self.date_start + timedelta(hours=2)
            # Only set therapist_end if not already provided
            if not self.therapist_end:
                self.therapist_end = self.date_end

    @api.onchange('date_end')
    def _onchange_date_end(self):
        """When event end changes:
        - therapist_end = max(therapist_end, date_end)
        """
        if self.date_end:
            # If therapist_end not set or earlier than date_end, align to date_end
            if not self.therapist_end or self.therapist_end < self.date_end:
                self.therapist_end = self.date_end

    @api.onchange('team_ids')
    def _onchange_team_ids_prefill_head_therapist(self):
        """When teams are selected, prefill assigned staff with head therapist users
        if none is assigned yet. Non-destructive: will not override existing selections.
        """
        if self.team_ids and not self.assigned_staff_ids:
            partners = self.team_ids.mapped('head_therapist_id')
            users = partners.mapped('user_ids').filtered(lambda u: u.active)
            if users:
                # Add the first active user (or multiple) without overriding future changes
                self.assigned_staff_ids = [(6, 0, users[:1].ids)]

    # ========================================
    # DEFAULTS / INITIALIZATION
    # ========================================
    @api.model
    def default_get(self, fields_list):
        """Initialize date_start/date_end from calendar selection when available.

        The calendar view for this model uses `therapist_start`/`therapist_end` as
        the date_start/date_stop fields. When a user selects a range and creates
        a new record from the calendar, Odoo puts those in context as
        `default_therapist_start` and `default_therapist_end`.

        We map them to `date_start`/`date_end` if those are not already provided
        in the defaults, so the form respects the selected range instead of
        overriding with field defaults or onchange logic.
        """
        values = super().default_get(fields_list)
        ctx = self.env.context or {}

        # Extract calendar-provided defaults
        cal_start = ctx.get('default_therapist_start')
        cal_end = ctx.get('default_therapist_end')

        # If the calendar provided a selection, prefer it over field defaults
        from datetime import timedelta
        if 'date_start' in self._fields and cal_start:
            values['date_start'] = cal_start
        if 'date_end' in self._fields:
            if cal_end:
                values['date_end'] = cal_end
            elif values.get('date_start') and not values.get('date_end'):
                # Provide a sensible default (+2 hours) if only start is given
                values['date_end'] = values['date_start'] + timedelta(hours=2)

        # Also ensure therapist_* align with provided calendar values if absent
        if 'therapist_start' in self._fields and not values.get('therapist_start') and cal_start:
            values['therapist_start'] = cal_start
        if 'therapist_end' in self._fields and not values.get('therapist_end'):
            if cal_end:
                values['therapist_end'] = cal_end
            elif values.get('date_end'):
                values['therapist_end'] = values['date_end']

        # Map legacy default_team_id context to team_ids for compatibility
        try:
            team_id_ctx = (self.env.context or {}).get('default_team_id')
            if team_id_ctx and 'team_ids' in self._fields and not values.get('team_ids'):
                values['team_ids'] = [(6, 0, [team_id_ctx])]
        except Exception:
            pass

        # Populate the TP user list at default-get time so the
        # assigned_staff_ids picker domain has values to filter on for a
        # brand-new event (the non-stored compute alone doesn't fire on a
        # NewId record before the form's domain is evaluated).
        if 'treatment_professional_user_ids' in fields_list and not values.get('treatment_professional_user_ids'):
            tp_internal = self.env.ref(
                'bemade_sports_clinic.group_sports_clinic_treatment_professional',
                raise_if_not_found=False,
            )
            tp_portal = self.env.ref(
                'bemade_sports_clinic.group_portal_treatment_professional',
                raise_if_not_found=False,
            )
            group_ids = [g.id for g in (tp_internal, tp_portal) if g]
            if group_ids:
                tp_user_ids = self.env['res.users'].search([
                    ('active', '=', True),
                    ('groups_id', 'in', group_ids),
                ]).ids
                values['treatment_professional_user_ids'] = [(6, 0, tp_user_ids)]

        return values

    # ========================================
    # VALIDATION
    # ========================================
    
    @api.constrains('date_start', 'date_end')
    def _check_event_dates(self):
        """Validate that end date is after start date"""
        for event in self:
            if event.date_start and event.date_end:
                if event.date_end <= event.date_start:
                    raise ValidationError("Event end time must be after start time.")
    
    @api.constrains('therapist_start', 'therapist_end')
    def _check_therapist_dates(self):
        """Validate that therapist end time is after start time"""
        for event in self:
            if event.therapist_start and event.therapist_end:
                if event.therapist_end <= event.therapist_start:
                    raise ValidationError("Therapist end time must be after start time.")
    
    # ========================================
    # PORTAL ACCESS METHODS
    # ========================================
    
    def check_portal_access(self, user=None):
        """Check if user has portal access to this event"""
        if not user:
            user = self.env.user
        
        # Internal users have full access
        if user.has_group('base.group_user'):
            return True
        
        # Portal treatment professionals need team access
        if user.has_group('bemade_sports_clinic.group_portal_treatment_professional'):
            partner = user.partner_id
            team_staff_rels = partner.team_staff_rel_ids
            authorized_teams = team_staff_rels.mapped('team_id')
            return bool(self.team_ids & authorized_teams)
        
        return False

    # ========================================
    # VALIDATION: ENFORCE SAME ORGANIZATION
    # ========================================
    @api.constrains('team_ids')
    def _check_team_ids_same_org_and_nonempty(self):
        for event in self:
            if not event.team_ids:
                raise ValidationError("Please select at least one team for the event.")
            orgs = event.team_ids.mapped('parent_id').filtered(lambda p: p)
            if orgs and len(set(orgs.mapped('id'))) > 1:
                raise ValidationError("All selected teams must belong to the same organization.")
    
    # ========================================
    # CRUD OVERRIDES
    # ========================================
    
    @api.model_create_multi
    def create(self, vals_list):
        events = super().create(vals_list)
        events.sudo()._sync_event_auto_staff()
        return events

    def write(self, vals):
        """Override write to enforce state change guardrails and keep
        the date_* / therapist_* time pairs in sync when one side
        moves alone (calendar drag updates only therapist_* because
        the calendar view is bound to those fields)."""
        if 'state' in vals:
            # Only internal users may change event state directly (statusbar)
            # Exception: portal cancellation is allowed via controller with context flag.
            if not self.env.user.has_group('base.group_user'):
                allow_portal_cancel = bool(self.env.context.get('portal_cancel_event'))
                if not allow_portal_cancel:
                    raise ValidationError("Only internal users can change event workflow state.")
            new_state = vals.get('state')
            allowed_states = {'confirmed', 'to_invoice', 'invoiced', 'cancelled'}
            if new_state not in allowed_states:
                raise ValidationError("Invalid state.")
            # Guardrails per record
            for event in self:
                # Prevent marking invoiced if customer side still needs invoicing
                if new_state == 'invoiced' and any(t.customer_ready_to_invoice for t in event.timesheet_ids):
                    raise ValidationError("Cannot mark Invoiced while timesheets remain to invoice.")
                # Portal may only cancel
                if not self.env.user.has_group('base.group_user') and new_state != 'cancelled':
                    raise ValidationError("Only internal users can change event workflow state.")

        # Drag-only sync: BOTH fields of a pair shifted together (the
        # calendar drag pattern) and the other pair wasn't touched.
        # We deliberately skip syncing when only one field of a pair
        # changed — that's a form edit where the user is adjusting one
        # boundary intentionally, and they don't want the other pair
        # auto-modified.
        sync_t_to_d = (
            'therapist_start' in vals and 'therapist_end' in vals
            and not ('date_start' in vals or 'date_end' in vals)
            and not self.env.context.get('skip_event_time_sync')
        )
        sync_d_to_t = (
            'date_start' in vals and 'date_end' in vals
            and not ('therapist_start' in vals or 'therapist_end' in vals)
            and not self.env.context.get('skip_event_time_sync')
        )
        old_times = {}
        if sync_t_to_d or sync_d_to_t:
            old_times = {
                e.id: {
                    'therapist_start': e.therapist_start,
                    'therapist_end': e.therapist_end,
                    'date_start': e.date_start,
                    'date_end': e.date_end,
                }
                for e in self
            }

        res = super().write(vals)

        if sync_t_to_d:
            for event in self.with_context(skip_event_time_sync=True):
                old = old_times.get(event.id, {})
                # Only shift if BOTH ends moved by the same delta — that
                # confirms a drag rather than two unrelated edits.
                if not (old.get('therapist_start') and old.get('therapist_end')
                        and event.therapist_start and event.therapist_end):
                    continue
                delta_start = event.therapist_start - old['therapist_start']
                delta_end = event.therapist_end - old['therapist_end']
                if delta_start != delta_end or not delta_start:
                    continue
                updates = {}
                if old.get('date_start'):
                    updates['date_start'] = old['date_start'] + delta_start
                if old.get('date_end'):
                    updates['date_end'] = old['date_end'] + delta_start
                if updates:
                    event.write(updates)
        elif sync_d_to_t:
            for event in self.with_context(skip_event_time_sync=True):
                old = old_times.get(event.id, {})
                if not (old.get('date_start') and old.get('date_end')
                        and event.date_start and event.date_end):
                    continue
                delta_start = event.date_start - old['date_start']
                delta_end = event.date_end - old['date_end']
                if delta_start != delta_end or not delta_start:
                    continue
                updates = {}
                if old.get('therapist_start'):
                    updates['therapist_start'] = old['therapist_start'] + delta_start
                if old.get('therapist_end'):
                    updates['therapist_end'] = old['therapist_end'] + delta_start
                if updates:
                    event.write(updates)

        if {'assigned_staff_ids', 'team_ids', 'state', 'date_end', 'therapist_end'}.intersection(vals):
            self.sudo()._sync_event_auto_staff()
        return res

    def unlink(self):
        # Detach this event from any auto-staff records, deleting orphans.
        Staff = self.env['sports.team.staff'].sudo()
        affected = Staff.search([('temporary_event_ids', 'in', self.ids)])
        affected.write({'temporary_event_ids': [(3, ev.id) for ev in self]})
        orphan_auto = affected.filtered(
            lambda s: s.is_auto_created and not s.temporary_event_ids
        )
        orphan_auto.unlink()
        return super().unlink()

    def _is_active_for_access(self):
        """An event is "active for access" while either the event itself
        or the therapist coverage window is still open (and the event is
        not cancelled). This way, extending therapist coverage past the
        event keeps the auto-grant alive for that extra time."""
        self.ensure_one()
        if self.state == 'cancelled':
            return False
        boundary = self.therapist_end or self.date_end
        if not boundary:
            return True
        return boundary >= fields.Datetime.now()

    def _sync_event_auto_staff(self):
        """For each event in self, reconcile sports.team.staff records used
        for temporary event-based access (task 539).

        - For active events: ensure each (team, assigned_user) pair has a
          staff record. If a manual record already exists, leave it alone.
          Otherwise create an auto-staff record (silent, role=therapist)
          and link this event in temporary_event_ids.
        - For inactive events (cancelled or past date_end): detach this
          event from existing auto-staff records; unlink any auto-staff
          left with no remaining temporary events.
        """
        Staff = self.env['sports.team.staff'].sudo()
        for event in self:
            prior = Staff.search([('temporary_event_ids', 'in', event.ids)])
            desired = set()
            if event._is_active_for_access():
                for team in event.team_ids:
                    for user in event.assigned_staff_ids:
                        if user.partner_id:
                            desired.add((team.id, user.partner_id.id))
            for team_id, partner_id in desired:
                existing = Staff.search([
                    ('team_id', '=', team_id),
                    ('partner_id', '=', partner_id),
                ], limit=1)
                if existing:
                    if existing.is_auto_created and event not in existing.temporary_event_ids:
                        existing.write({'temporary_event_ids': [(4, event.id)]})
                else:
                    Staff.create({
                        'team_id': team_id,
                        'partner_id': partner_id,
                        'role': 'therapist',
                        'is_auto_created': True,
                        'silent_notifications': True,
                        'temporary_event_ids': [(4, event.id)],
                    })
            for staff in prior:
                if (staff.team_id.id, staff.partner_id.id) not in desired:
                    staff.write({'temporary_event_ids': [(3, event.id)]})
                    if staff.is_auto_created and not staff.temporary_event_ids:
                        staff.unlink()

    @api.model
    def _cron_cleanup_auto_event_staff(self):
        """Nightly: detach past or cancelled events from auto-staff and
        unlink orphans. Runs _sync_event_auto_staff which is idempotent.

        An event is "stale" when both the event window and the
        therapist coverage window have passed (or it's cancelled).
        Picking up records by either boundary keeps the cleanup eager
        without missing events whose coverage already ended even though
        date_end hasn't.
        """
        now = fields.Datetime.now()
        stale = self.search([
            '|',
                ('state', '=', 'cancelled'),
                '&',
                    ('date_end', '<', now),
                    '|',
                        ('therapist_end', '=', False),
                        ('therapist_end', '<', now),
        ])
        if stale:
            stale._sync_event_auto_staff()

    def _update_state_from_timesheets(self):
        """Update the event workflow state based on timesheet billing progress.

        Rules:
        - Cancelled events stay cancelled (unless manually marked invoiced by an internal user).
        - If all timesheets are invoiced -> invoiced
        - Else if any timesheet is ready to invoice (customer) -> to_invoice
        - Else -> confirmed
        """
        for event in self:
            if event.state == 'cancelled':
                continue
            ts = event.timesheet_ids
            if ts and all(t.state == 'invoiced' for t in ts):
                if event.state != 'invoiced':
                    try:
                        event.with_context(allow_task_sync=True).write({'state': 'invoiced'})
                    except Exception:
                        pass
                continue
            if any(t.customer_ready_to_invoice for t in ts):
                if event.state != 'to_invoice':
                    try:
                        event.with_context(allow_task_sync=True).write({'state': 'to_invoice'})
                    except Exception:
                        pass
            else:
                if event.state != 'confirmed':
                    try:
                        event.with_context(allow_task_sync=True).write({'state': 'confirmed'})
                    except Exception:
                        pass
    
    # ========================================
    # INTERNAL WORKFLOW ACTIONS
    # ========================================
    def action_cancel(self):
        """Cancel an event (internal users only)."""
        internal_user = self.env.user.has_group('base.group_user')
        if not internal_user:
            raise ValidationError("Only internal users can cancel events.")
        for event in self:
            if event.state != 'cancelled':
                event.write({'state': 'cancelled'})
                try:
                    event.message_post(body="Event cancelled")
                except Exception:
                    pass
        return True

    def action_revive(self):
        """Revive a cancelled event back to confirmed (internal users only)."""
        internal_user = self.env.user.has_group('base.group_user')
        if not internal_user:
            raise ValidationError("Only internal users can revive events.")
        for event in self:
            if event.state == 'cancelled':
                event.write({'state': 'confirmed'})
                try:
                    event.message_post(body="Event revived to Confirmed")
                except Exception:
                    pass
                event._update_state_from_timesheets()
        return True

    # ========================================
    # HELPERS
    # ========================================
    def _get_missing_timesheet_user_ids(self):
        """Return res.users records for assigned staff who do not have a timesheet yet"""
        self.ensure_one()
        assigned = self.assigned_staff_ids
        if not assigned:
            return self.env['res.users']
        have_ts_users = self.timesheet_ids.mapped('user_id')
        missing = assigned - have_ts_users
        return missing

    def action_mark_invoiced(self):
        """Mark event as Invoiced (internal users only). Typically done after billing."""
        internal_user = self.env.user.has_group('base.group_user')
        if not internal_user:
            raise ValidationError("Only internal users can change event workflow state.")
        for event in self:
            # Allow invoiced from to_invoice or cancelled (if billed anyway), and idempotent
            if event.state in ('to_invoice', 'cancelled', 'invoiced'):
                event.write({'state': 'invoiced'})
                try:
                    event.message_post(body="Event marked Invoiced")
                except Exception:
                    pass
        return True

    def action_reset_unlinked_timesheets(self):
        """Reset timesheets to 'submitted' if they are no longer linked to any SO/PO/Invoice lines.

        This is useful when SO/PO lines were deleted and timesheets need to be reprocessed.
        """
        self.ensure_one()
        ts = self.timesheet_ids
        before = len(ts.filtered(lambda t: t.state == 'invoiced'))
        ts.action_reset_if_unlinked()
        after = len(ts.filtered(lambda t: t.state == 'invoiced'))
        reset_count = before - after
        # If any timesheets were reset, move event to 'to_invoice' to enable Add to SO actions
        if reset_count > 0:
            try:
                self.write({'state': 'to_invoice'})
            except Exception:
                pass
        try:
            self.message_post(body=f"Reset {reset_count} timesheet(s) to Submitted where unlinked.")
        except Exception:
            pass
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': f"Reset {reset_count} timesheet(s) to Submitted.",
                'type': 'success',
            }
        }
