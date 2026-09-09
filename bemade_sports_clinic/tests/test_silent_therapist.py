"""Tests for the 'silent' therapist flag (task 911).

Acceptance criteria:
- A sports.team.staff record can be flagged silent (silent_notifications=True).
- A silent staff member's partner is NOT auto-subscribed as a follower of
  the team's patients (or their injuries).
- A non-silent staff member IS auto-subscribed (existing behaviour).
- Toggling the flag from non-silent → silent unsubscribes; from silent →
  non-silent subscribes.
- Access (security group membership and record-rule visibility) is
  unaffected by the silent flag — silent therapists still get TP group
  and can see/edit patients per the normal rules.
"""

from odoo.tests import TransactionCase, tagged


@tagged("-at_install", "post_install")
class TestSilentTherapist(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tp_group_internal = cls.env.ref(
            "bemade_sports_clinic.group_sports_clinic_treatment_professional"
        )
        cls.team = cls.env["sports.team"].create({"name": "Silent Test Team"})
        cls.player = cls.env["sports.patient"].create({
            "first_name": "Silent", "last_name": "Player",
            "team_ids": [(6, 0, [cls.team.id])],
        })
        cls.tp_user = cls.env["res.users"].create({
            "name": "Silent TP", "login": "silent.tp@example.com",
            "groups_id": [(6, 0, [cls.env.ref("base.group_user").id])],
        })

    def _staff(self, **vals):
        return self.env["sports.team.staff"].create({
            "team_id": self.team.id,
            "partner_id": self.tp_user.partner_id.id,
            "role": "therapist",
            **vals,
        })

    def test_silent_staff_not_subscribed_as_follower(self):
        self._staff(silent_notifications=True)
        self.assertNotIn(
            self.tp_user.partner_id, self.player.message_partner_ids,
        )

    def test_non_silent_staff_subscribed_as_follower(self):
        self._staff(silent_notifications=False)
        self.assertIn(
            self.tp_user.partner_id, self.player.message_partner_ids,
        )

    def test_toggle_silent_to_non_silent_subscribes(self):
        staff = self._staff(silent_notifications=True)
        self.assertNotIn(
            self.tp_user.partner_id, self.player.message_partner_ids,
        )
        staff.write({"silent_notifications": False})
        self.assertIn(
            self.tp_user.partner_id, self.player.message_partner_ids,
        )

    def test_toggle_non_silent_to_silent_unsubscribes(self):
        staff = self._staff(silent_notifications=False)
        self.assertIn(
            self.tp_user.partner_id, self.player.message_partner_ids,
        )
        staff.write({"silent_notifications": True})
        self.assertNotIn(
            self.tp_user.partner_id, self.player.message_partner_ids,
        )

    def test_silent_staff_still_gets_tp_group(self):
        self._staff(silent_notifications=True)
        self.tp_user.invalidate_recordset(["groups_id"])
        self.assertIn(self.tp_group_internal, self.tp_user.groups_id)

    def test_silent_staff_can_still_read_team_patients(self):
        self._staff(silent_notifications=True)
        visible = (
            self.env["sports.patient"]
            .with_user(self.tp_user)
            .search([("id", "=", self.player.id)])
        )
        self.assertEqual(visible, self.player)
