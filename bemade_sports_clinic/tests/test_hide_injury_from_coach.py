"""Tests for the 'hide injury from coach' flag (task 887).

Acceptance criteria:
- A sports.patient.injury can be flagged hidden_from_coaches=True.
- A portal team coach assigned to the patient's team CANNOT see hidden
  injuries (they fall out of search results / raise AccessError on read).
- The same coach CAN see non-hidden injuries on the same patient.
- Internal treatment professionals see both hidden and non-hidden.
- Internal admins see both.
- Toggling the flag back to False makes the injury visible to the coach
  again.
"""

from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


@tagged("-at_install", "post_install")
class TestHideInjuryFromCoach(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.team = cls.env["sports.team"].create({"name": "Hide Injury Team"})
        cls.player = cls.env["sports.patient"].create({
            "first_name": "HI", "last_name": "Player",
            "team_ids": [(6, 0, [cls.team.id])],
        })

        cls.coach_user = cls.env["res.users"].with_context(
            no_reset_password=True
        ).create({
            "name": "Test Coach",
            "login": "test.coach.887@example.com",
            "groups_id": [(6, 0, [
                cls.env.ref("base.group_portal").id,
                cls.env.ref("bemade_sports_clinic.group_portal_team_coach").id,
            ])],
        })
        cls.env["sports.team.staff"].create({
            "team_id": cls.team.id,
            "partner_id": cls.coach_user.partner_id.id,
            "role": "coach",
        })

        cls.tp_user = cls.env["res.users"].create({
            "name": "Test TP",
            "login": "test.tp.887@example.com",
            "groups_id": [(6, 0, [
                cls.env.ref("base.group_user").id,
                cls.env.ref("bemade_sports_clinic.group_sports_clinic_treatment_professional").id,
            ])],
        })
        cls.env["sports.team.staff"].create({
            "team_id": cls.team.id,
            "partner_id": cls.tp_user.partner_id.id,
            "role": "therapist",
        })

        cls.normal_injury = cls.env["sports.patient.injury"].create({
            "patient_id": cls.player.id,
            "diagnosis": "Visible injury",
            "stage": "active",
        })
        cls.hidden_injury = cls.env["sports.patient.injury"].create({
            "patient_id": cls.player.id,
            "diagnosis": "Hidden injury",
            "stage": "active",
            "hidden_from_coaches": True,
        })

    def _coach_can_see(self, injury):
        try:
            return bool(
                self.env["sports.patient.injury"]
                .with_user(self.coach_user)
                .search([("id", "=", injury.id)])
            )
        except AccessError:
            return False

    def test_coach_sees_non_hidden_injury(self):
        self.assertTrue(self._coach_can_see(self.normal_injury))

    def test_coach_does_not_see_hidden_injury(self):
        self.assertFalse(self._coach_can_see(self.hidden_injury))

    def test_coach_cannot_read_hidden_injury_directly(self):
        with self.assertRaises(AccessError):
            self.hidden_injury.with_user(self.coach_user).read(["diagnosis"])

    def test_tp_sees_both(self):
        visible = (
            self.env["sports.patient.injury"]
            .with_user(self.tp_user)
            .search([("patient_id", "=", self.player.id)])
        )
        self.assertIn(self.normal_injury, visible)
        self.assertIn(self.hidden_injury, visible)

    def test_admin_sees_both(self):
        admin = self.env.ref("base.user_admin")
        visible = (
            self.env["sports.patient.injury"]
            .with_user(admin)
            .search([("patient_id", "=", self.player.id)])
        )
        self.assertIn(self.normal_injury, visible)
        self.assertIn(self.hidden_injury, visible)

    def test_toggle_unhides_for_coach(self):
        self.assertFalse(self._coach_can_see(self.hidden_injury))
        self.hidden_injury.write({"hidden_from_coaches": False})
        self.assertTrue(self._coach_can_see(self.hidden_injury))
