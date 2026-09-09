"""Tests for auto-grant therapist team access on event coverage (task 539).

Acceptance criteria:
- When a TP is added to sports.event.assigned_staff_ids and the event
  covers a team, a sports.team.staff record is auto-created on that team
  for the TP, marked is_auto_created=True with the event in
  temporary_event_ids. The TP can immediately read the team's patients.
- Auto-created records are silent (silent_notifications=True) so they do
  not subscribe the TP as follower of the team's patients.
- Removing a TP from event.assigned_staff_ids: the corresponding event is
  removed from temporary_event_ids on each (team, user) staff record;
  records that were is_auto_created=True with no remaining
  temporary_event_ids are unlinked.
- If the same TP covers multiple events on the same team, the auto-staff
  record carries all those events in temporary_event_ids; removal of one
  event does not delete the record while others remain.
- Setting event.state = 'cancelled' triggers the same revoke flow as
  removing the staff manually.
- Past events (date_end < now) cause cleanup via cron, even if state is
  still 'confirmed'.
- An existing MANUAL staff record (is_auto_created=False) is not touched
  by event grants — no temporary_event_ids tracking added, the record is
  not unlinked when the event ends, and the TP keeps any pre-existing
  silent_notifications setting.
"""

from datetime import datetime, timedelta
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


@tagged("-at_install", "post_install")
class TestEventAutoAccess(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.team_a = cls.env["sports.team"].create({"name": "Auto Team A"})
        cls.team_b = cls.env["sports.team"].create({"name": "Auto Team B"})
        cls.player_a = cls.env["sports.patient"].create({
            "first_name": "PA", "last_name": "Auto",
            "team_ids": [(6, 0, [cls.team_a.id])],
        })
        cls.tp_user = cls.env["res.users"].create({
            "name": "Event TP", "login": "event.tp@example.com",
            "groups_id": [(6, 0, [
                cls.env.ref("base.group_user").id,
                cls.env.ref("bemade_sports_clinic.group_sports_clinic_treatment_professional").id,
            ])],
        })

    def _make_event(self, teams, users, **vals):
        return self.env["sports.event"].create({
            "name": vals.pop("name", "E"),
            "date_start": vals.pop("date_start", datetime.now() + timedelta(hours=1)),
            "date_end": vals.pop("date_end", datetime.now() + timedelta(hours=3)),
            "team_ids": [(6, 0, teams.ids)],
            "assigned_staff_ids": [(6, 0, users.ids)],
            **vals,
        })

    def _staff_for(self, team, user):
        return self.env["sports.team.staff"].search([
            ("team_id", "=", team.id),
            ("partner_id", "=", user.partner_id.id),
        ], limit=1)

    def _can_see(self, user, patient):
        try:
            return bool(
                self.env["sports.patient"]
                .with_user(user)
                .search([("id", "=", patient.id)])
            )
        except AccessError:
            return False

    def test_assign_creates_auto_staff(self):
        event = self._make_event(self.team_a, self.tp_user)
        staff = self._staff_for(self.team_a, self.tp_user)
        self.assertTrue(staff)
        self.assertTrue(staff.is_auto_created)
        self.assertIn(event, staff.temporary_event_ids)
        self.assertTrue(staff.silent_notifications)
        self.assertTrue(self._can_see(self.tp_user, self.player_a))

    def test_unassign_removes_auto_staff(self):
        event = self._make_event(self.team_a, self.tp_user)
        self.assertTrue(self._staff_for(self.team_a, self.tp_user))
        event.write({"assigned_staff_ids": [(5,)]})
        self.assertFalse(self._staff_for(self.team_a, self.tp_user))
        self.assertFalse(self._can_see(self.tp_user, self.player_a))

    def test_multi_event_same_team_keeps_record(self):
        e1 = self._make_event(self.team_a, self.tp_user, name="E1")
        e2 = self._make_event(self.team_a, self.tp_user, name="E2")
        staff = self._staff_for(self.team_a, self.tp_user)
        self.assertEqual(staff.temporary_event_ids, e1 | e2)
        e1.write({"assigned_staff_ids": [(5,)]})
        staff = self._staff_for(self.team_a, self.tp_user)
        self.assertTrue(staff)
        self.assertEqual(staff.temporary_event_ids, e2)

    def test_event_cancel_removes_auto_staff(self):
        event = self._make_event(self.team_a, self.tp_user)
        self.assertTrue(self._staff_for(self.team_a, self.tp_user))
        event.write({"state": "cancelled"})
        self.assertFalse(self._staff_for(self.team_a, self.tp_user))

    def test_past_event_cron_cleanup(self):
        event = self._make_event(self.team_a, self.tp_user)
        self.assertTrue(self._staff_for(self.team_a, self.tp_user))
        # Backdate date_end to simulate a past event without re-triggering
        # the write-time sync (which would clean up immediately).
        event.invalidate_recordset(["date_end"])
        self.env.cr.execute(
            "UPDATE sports_event SET date_end = %s WHERE id = %s",
            (datetime.now() - timedelta(hours=1), event.id),
        )
        event.invalidate_recordset(["date_end"])
        # Staff should still exist until cron runs
        self.assertTrue(self._staff_for(self.team_a, self.tp_user))
        self.env["sports.event"]._cron_cleanup_auto_event_staff()
        self.assertFalse(self._staff_for(self.team_a, self.tp_user))

    def test_manual_staff_not_touched_by_event_assignment(self):
        manual = self.env["sports.team.staff"].create({
            "team_id": self.team_a.id,
            "partner_id": self.tp_user.partner_id.id,
            "role": "therapist",
        })
        event = self._make_event(self.team_a, self.tp_user)
        # No new staff created; manual record stays as-is
        self.assertEqual(self._staff_for(self.team_a, self.tp_user), manual)
        self.assertFalse(manual.is_auto_created)
        self.assertFalse(manual.temporary_event_ids)
        # Removing user from event does NOT unlink the manual record
        event.write({"assigned_staff_ids": [(5,)]})
        self.assertTrue(manual.exists())
        self.assertEqual(self._staff_for(self.team_a, self.tp_user), manual)
