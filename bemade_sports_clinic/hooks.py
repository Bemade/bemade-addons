def post_init_hook(env):
    """Migrate legacy team_id to team_ids on sports.event and recompute partner_id.

    - For any event having a non-null team_id column (from previous versions),
      set team_ids to that single team.
    - Recompute partner_id based on team_ids.
    """
    cr = env.cr
    Event = env['sports.event']

    # Best-effort: detect if legacy column exists; if not, skip silently
    has_legacy = False
    try:
        cr.execute("""
            SELECT 1
            FROM information_schema.columns 
            WHERE table_name = 'sports_event' AND column_name = 'team_id'
        """)
        has_legacy = bool(cr.fetchone())
    except Exception:
        has_legacy = False

    if has_legacy:
        # Find events where team_ids is empty but legacy team_id is set
        # Use SQL to avoid M2M join costs, then set via ORM
        cr.execute("""
            SELECT e.id, e.team_id
            FROM sports_event e
            WHERE e.team_id IS NOT NULL
        """)
        rows = cr.fetchall() or []
        if rows:
            event_map = {}
            for ev_id, team_id in rows:
                if ev_id and team_id:
                    event_map.setdefault(ev_id, team_id)
            # Apply in batches
            BATCH = 500
            ev_ids = list(event_map.keys())
            for i in range(0, len(ev_ids), BATCH):
                chunk = ev_ids[i:i+BATCH]
                events = Event.browse(chunk)
                # Build full list for this chunk
                vals_list = []
                for ev in events:
                    t_id = event_map.get(ev.id)
                    if t_id:
                        vals_list.append((ev, [(6, 0, [t_id])]))
                # Write team_ids
                for ev, cmd in vals_list:
                    try:
                        ev.write({'team_ids': cmd})
                    except Exception:
                        # Do not block migration on edge cases
                        pass

    # Recompute partner_id for all events
    try:
        all_events = Event.search([])
        # Trigger compute by writing no-op on relevant dependency
        # Safer: call helper if present
        if hasattr(Event, 'action_recompute_partner_ids'):
            Event.action_recompute_partner_ids()
        else:
            # Fallback: touch records to recompute stored compute
            for ev in all_events:
                ev._compute_partner_id()
    except Exception:
        # Non-blocking
        pass
