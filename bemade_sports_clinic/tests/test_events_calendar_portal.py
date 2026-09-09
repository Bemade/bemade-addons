"""Tests for the events calendar portal page (task 611).

Acceptance criteria:
- A team coach can hit /my/events/calendar and gets a 200 OK rendering
  the calendar shell.
- /my/events/calendar/data?start=...&end=... returns JSON of events
  scoped to the user (coaches see only events for teams they're staff
  on; therapists see all). Past events are included.
- Anonymous users are bounced to login.
- A regular portal user with no clinic role gets no events from the
  data endpoint.
"""

import json
from datetime import datetime, timedelta

from odoo import Command
from odoo.tests import HttpCase, tagged


@tagged("-at_install", "post_install")
class TestEventsCalendarPortal(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.team_a = cls.env["sports.team"].create({"name": "Cal Team A"})
        cls.team_b = cls.env["sports.team"].create({"name": "Cal Team B"})

        # Coach assigned to team_a only
        cls.coach_user = cls.env["res.users"].with_context(
            no_reset_password=True
        ).create({
            "name": "Cal Coach",
            "login": "cal.coach.611@example.com",
            "password": "cal-coach",
            "groups_id": [
                Command.set([
                    cls.env.ref("base.group_portal").id,
                    cls.env.ref("bemade_sports_clinic.group_portal_team_coach").id,
                ]),
            ],
        })
        cls.env["sports.team.staff"].create({
            "team_id": cls.team_a.id,
            "partner_id": cls.coach_user.partner_id.id,
            "role": "coach",
        })

        # Internal therapist (sees all)
        cls.therapist_user = cls.env["res.users"].with_context(
            no_reset_password=True
        ).create({
            "name": "Cal TP",
            "login": "cal.tp.611@example.com",
            "password": "cal-tp",
            "groups_id": [
                Command.set([
                    cls.env.ref("base.group_user").id,
                    cls.env.ref("bemade_sports_clinic.group_sports_clinic_treatment_professional").id,
                ]),
            ],
        })

        # Plain portal user with no clinic role
        cls.plain_user = cls.env["res.users"].with_context(
            no_reset_password=True
        ).create({
            "name": "Plain User",
            "login": "plain.611@example.com",
            "password": "plain",
            "groups_id": [Command.set([cls.env.ref("base.group_portal").id])],
        })

        now = datetime.now()
        cls.future_a = cls.env["sports.event"].create({
            "name": "Future Team A",
            "team_ids": [(6, 0, [cls.team_a.id])],
            "date_start": now + timedelta(days=2),
            "date_end": now + timedelta(days=2, hours=2),
        })
        cls.past_a = cls.env["sports.event"].create({
            "name": "Past Team A",
            "team_ids": [(6, 0, [cls.team_a.id])],
            "date_start": now - timedelta(days=10),
            "date_end": now - timedelta(days=10, hours=-2),
        })
        cls.future_b = cls.env["sports.event"].create({
            "name": "Future Team B",
            "team_ids": [(6, 0, [cls.team_b.id])],
            "date_start": now + timedelta(days=3),
            "date_end": now + timedelta(days=3, hours=2),
        })

    def _get_data(self, start, end):
        url = (
            f"/my/events/calendar/data"
            f"?start={start.isoformat()}&end={end.isoformat()}"
        )
        return self.url_open(url)

    def test_coach_can_open_calendar_page(self):
        self.authenticate("cal.coach.611@example.com", "cal-coach")
        resp = self.url_open("/my/events/calendar")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"portal-events-calendar", resp.content)

    def test_coach_data_endpoint_filters_to_their_teams(self):
        self.authenticate("cal.coach.611@example.com", "cal-coach")
        start = datetime.now() - timedelta(days=30)
        end = datetime.now() + timedelta(days=30)
        resp = self._get_data(start, end)
        self.assertEqual(resp.status_code, 200)
        events = resp.json()
        ids = {e["id"] for e in events}
        self.assertIn(self.future_a.id, ids)
        self.assertIn(self.past_a.id, ids)
        self.assertNotIn(self.future_b.id, ids)

    def test_therapist_data_endpoint_sees_all(self):
        self.authenticate("cal.tp.611@example.com", "cal-tp")
        start = datetime.now() - timedelta(days=30)
        end = datetime.now() + timedelta(days=30)
        resp = self._get_data(start, end)
        events = resp.json()
        ids = {e["id"] for e in events}
        self.assertIn(self.future_a.id, ids)
        self.assertIn(self.past_a.id, ids)
        self.assertIn(self.future_b.id, ids)

    def test_plain_portal_user_data_empty(self):
        self.authenticate("plain.611@example.com", "plain")
        start = datetime.now() - timedelta(days=30)
        end = datetime.now() + timedelta(days=30)
        resp = self._get_data(start, end)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json(), [])

    def test_event_payload_carries_basics(self):
        """Each event should at minimum carry id, title, start, end so
        FullCalendar can render it; team and assigned-staff names should
        be available for the popover."""
        self.authenticate("cal.coach.611@example.com", "cal-coach")
        start = datetime.now() - timedelta(days=30)
        end = datetime.now() + timedelta(days=30)
        events = self._get_data(start, end).json()
        e = next(e for e in events if e["id"] == self.future_a.id)
        for k in ("id", "title", "start", "end", "url"):
            self.assertIn(k, e)
        self.assertIn("teams", e.get("extendedProps", {}))

    def test_event_payload_start_end_are_explicit_utc(self):
        """Payload start/end must be ISO-8601 with an explicit UTC offset
        (or trailing 'Z'). Emitting Odoo's bare 'YYYY-MM-DD HH:MM:SS'
        leads FullCalendar to treat the wall-clock as already-local,
        shifting every event by the client's UTC offset (the 11 AM →
        3 PM bug Stephanie reported in EDT)."""
        self.authenticate("cal.coach.611@example.com", "cal-coach")
        start = datetime.now() - timedelta(days=30)
        end = datetime.now() + timedelta(days=30)
        events = self._get_data(start, end).json()
        e = next(e for e in events if e["id"] == self.future_a.id)
        # ISO-8601 UTC marker check: '+00:00' (what isoformat emits for
        # a pytz.UTC-localized datetime) or 'Z' both qualify.
        self.assertTrue(
            e["start"].endswith("+00:00") or e["start"].endswith("Z"),
            f"start should carry an explicit UTC marker, got {e['start']!r}",
        )
        self.assertTrue(
            e["end"].endswith("+00:00") or e["end"].endswith("Z"),
            f"end should carry an explicit UTC marker, got {e['end']!r}",
        )
        # Round-trip: parsed start should match the UTC datetime stored
        # on the event, regardless of any client-side offset rendering.
        parsed = datetime.fromisoformat(e["start"].replace("Z", "+00:00"))
        self.assertEqual(
            parsed.utcoffset().total_seconds(), 0,
            "Parsed payload datetime must be UTC.",
        )
        # Strip tz to compare with Odoo's naive-UTC stored value.
        self.assertEqual(
            parsed.replace(tzinfo=None).replace(microsecond=0),
            self.future_a.date_start.replace(microsecond=0),
        )
