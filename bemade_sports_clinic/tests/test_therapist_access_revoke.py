"""Tests for therapist access lifecycle on team-staff removal.

Acceptance criteria:
- When a therapist's sports.team.staff record is unlinked (or role flipped
  away from a therapist role), and they have no remaining therapist roles
  on any other team:
    * They lose group_sports_clinic_treatment_professional (internal) or
      group_portal_treatment_professional (portal).
    * Internal: record-rule access to sports.patient / sports.team /
      sports.patient.injury for the team's records is denied.
    * Portal: record-rule access to sports.patient and sports.team is
      denied (portal TPs have an unrestricted rule keyed off the portal
      TP group, so removal of the group is what cuts access).
    * They are unsubscribed from the team's patients' followers.
- When the therapist still has a therapist role on at least one other
  team, group membership and record-rule access for THAT team's records
  are preserved.
"""

from odoo.tests import TransactionCase, tagged
from odoo.exceptions import AccessError


@tagged("-at_install", "post_install")
class TestTherapistAccessRevoke(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.tp_group_internal = cls.env.ref(
            "bemade_sports_clinic.group_sports_clinic_treatment_professional"
        )
        cls.tp_group_portal = cls.env.ref(
            "bemade_sports_clinic.group_portal_treatment_professional"
        )

        cls.team_a = cls.env["sports.team"].create({"name": "Team A"})
        cls.team_b = cls.env["sports.team"].create({"name": "Team B"})

        cls.player_a = cls.env["sports.patient"].create({
            "first_name": "Pat", "last_name": "A",
            "team_ids": [(6, 0, [cls.team_a.id])],
        })
        cls.player_b = cls.env["sports.patient"].create({
            "first_name": "Pat", "last_name": "B",
            "team_ids": [(6, 0, [cls.team_b.id])],
        })

        cls.internal_tp = cls.env["res.users"].create({
            "name": "Internal TP", "login": "tp.internal@example.com",
            "groups_id": [(6, 0, [cls.env.ref("base.group_user").id])],
        })
        cls.portal_tp = cls.env["res.users"].create({
            "name": "Portal TP", "login": "tp.portal@example.com",
            "groups_id": [(6, 0, [cls.env.ref("base.group_portal").id])],
        })

    def _staff(self, user, team, role="therapist"):
        return self.env["sports.team.staff"].create({
            "team_id": team.id,
            "partner_id": user.partner_id.id,
            "role": role,
        })

    def _can_see(self, user, patient):
        """True iff search([id=patient.id]) returns the record under user."""
        return bool(
            self.env["sports.patient"]
            .with_user(user)
            .search([("id", "=", patient.id)])
        )

    # --- Internal TP --------------------------------------------------

    def test_internal_tp_loses_group_on_only_role_unlink(self):
        staff = self._staff(self.internal_tp, self.team_a)
        self.assertIn(self.tp_group_internal, self.internal_tp.groups_id)
        staff.unlink()
        self.internal_tp.invalidate_recordset(["groups_id"])
        self.assertNotIn(self.tp_group_internal, self.internal_tp.groups_id)

    def test_internal_tp_loses_patient_access_on_unlink(self):
        staff = self._staff(self.internal_tp, self.team_a)
        self.assertTrue(self._can_see(self.internal_tp, self.player_a))
        staff.unlink()
        self.internal_tp.invalidate_recordset(["groups_id"])
        # Internal TP loses both ACL and rule — search raises AccessError
        with self.assertRaises(AccessError):
            self.env["sports.patient"].with_user(self.internal_tp).search([])

    def test_internal_tp_keeps_access_when_still_on_other_team(self):
        staff_a = self._staff(self.internal_tp, self.team_a)
        self._staff(self.internal_tp, self.team_b)
        staff_a.unlink()
        self.internal_tp.invalidate_recordset(["groups_id"])
        self.assertIn(self.tp_group_internal, self.internal_tp.groups_id)
        self.assertTrue(self._can_see(self.internal_tp, self.player_b))
        self.assertFalse(self._can_see(self.internal_tp, self.player_a))

    def test_internal_tp_loses_access_on_role_change_away(self):
        staff = self._staff(self.internal_tp, self.team_a)
        staff.write({"role": "other"})
        self.internal_tp.invalidate_recordset(["groups_id"])
        self.assertNotIn(self.tp_group_internal, self.internal_tp.groups_id)
        with self.assertRaises(AccessError):
            self.env["sports.patient"].with_user(self.internal_tp).search([])

    def test_internal_tp_unsubscribed_from_team_patients_on_unlink(self):
        staff = self._staff(self.internal_tp, self.team_a)
        self.assertIn(
            self.internal_tp.partner_id, self.player_a.message_partner_ids,
        )
        staff.unlink()
        self.assertNotIn(
            self.internal_tp.partner_id, self.player_a.message_partner_ids,
        )

    # --- Portal TP ----------------------------------------------------

    def test_portal_tp_loses_group_on_only_role_unlink(self):
        staff = self._staff(self.portal_tp, self.team_a)
        self.assertIn(self.tp_group_portal, self.portal_tp.groups_id)
        staff.unlink()
        self.portal_tp.invalidate_recordset(["groups_id"])
        self.assertNotIn(self.tp_group_portal, self.portal_tp.groups_id)

    def test_portal_tp_loses_patient_access_on_unlink(self):
        staff = self._staff(self.portal_tp, self.team_a)
        # Portal TP rule grants access via team-staff membership.
        self.assertTrue(self._can_see(self.portal_tp, self.player_a))
        staff.unlink()
        self.portal_tp.invalidate_recordset(["groups_id"])
        # Group revoked + no remaining staff record → no access.
        self.assertFalse(self._can_see(self.portal_tp, self.player_a))

    def test_portal_tp_keeps_access_when_still_on_other_team(self):
        staff_a = self._staff(self.portal_tp, self.team_a)
        self._staff(self.portal_tp, self.team_b)
        staff_a.unlink()
        self.portal_tp.invalidate_recordset(["groups_id"])
        self.assertIn(self.tp_group_portal, self.portal_tp.groups_id)
        # Tightened in 18.0.3.6.1: TPs are scoped to teams they staff.
        # After removal from team_a, they keep team_b access only.
        self.assertFalse(self._can_see(self.portal_tp, self.player_a))
        self.assertTrue(self._can_see(self.portal_tp, self.player_b))

    def test_portal_tp_unsubscribed_from_team_patients_on_unlink(self):
        staff = self._staff(self.portal_tp, self.team_a)
        self.assertIn(
            self.portal_tp.partner_id, self.player_a.message_partner_ids,
        )
        staff.unlink()
        self.assertNotIn(
            self.portal_tp.partner_id, self.player_a.message_partner_ids,
        )

    # --- Stale mail.activity cleanup ----------------------------------

    def _injury(self, patient, team):
        return self.env["sports.patient.injury"].create({
            "patient_id": patient.id,
            "team_id": team.id,
            "diagnosis": "Test injury",
            "stage": "active",
        })

    def _activity_on(self, injury, user):
        return self.env["mail.activity"].create({
            "res_model_id": self.env["ir.model"]._get_id("sports.patient.injury"),
            "res_id": injury.id,
            "summary": "Verify injury",
            "user_id": user.id,
            "date_deadline": "2026-05-15",
        })

    def test_portal_tp_stale_activity_reassigned_on_unlink(self):
        """When a portal TP is removed from one team but still on another,
        mail.activity records on the ex-team's injuries should follow the
        team — reassigned to the team's head therapist — not stay
        assigned to a user whose record-rule scope no longer covers the
        related injury (which would trigger a 403 on /my/activities when
        the template browses the related injury)."""
        head_tp = self.env["res.users"].create({
            "name": "Head TP",
            "login": "head.tp@example.com",
            "groups_id": [(6, 0, [self.env.ref("base.group_portal").id])],
        })
        self._staff(head_tp, self.team_a, role="head_therapist")
        ex_staff = self._staff(self.portal_tp, self.team_a)
        # Portal TP also staffs team_b — keeps her portal-TP group + ACL on
        # mail.activity after the team_a removal.
        self._staff(self.portal_tp, self.team_b)
        injury = self._injury(self.player_a, self.team_a)
        activity = self._activity_on(injury, self.portal_tp)

        ex_staff.unlink()

        activity.invalidate_recordset(["user_id"])
        self.assertEqual(
            activity.user_id, head_tp,
            "Stale activity should be reassigned to the team's head therapist.",
        )
        # Ex-TP can still query mail.activity (other teams remain), but
        # this orphan one is filtered out by the rule.
        self.portal_tp.invalidate_recordset(["groups_id"])
        visible = (
            self.env["mail.activity"]
            .with_user(self.portal_tp)
            .search([("id", "=", activity.id)])
        )
        self.assertFalse(
            visible,
            "Ex-TP must not see activities for injuries off her teams "
            "(prevents 403 in /my/activities when the template browses "
            "the related injury).",
        )

    def test_portal_tp_stale_activity_dropped_when_no_replacement(self):
        """If no current team therapist exists to take over, the stale
        activity is unlinked rather than left assigned to a user who
        can no longer act on it."""
        ex_staff = self._staff(self.portal_tp, self.team_a)
        injury = self._injury(self.player_a, self.team_a)
        activity = self._activity_on(injury, self.portal_tp)
        activity_id = activity.id

        ex_staff.unlink()

        self.assertFalse(
            self.env["mail.activity"].browse(activity_id).exists(),
            "Activity should be unlinked when there's no current team "
            "therapist to take it over.",
        )

    # --- Self-healing path --------------------------------------------

    def test_orphan_tp_group_cleared_by_nightly_recompute(self):
        """If a user has the portal TP group but no staff records, the
        nightly cron action_recompute_sports_followers_and_groups should
        revoke it. Guards the nightly self-healing path."""
        self.portal_tp.sudo().write({
            "groups_id": [(4, self.tp_group_portal.id)],
        })
        self.assertIn(self.tp_group_portal, self.portal_tp.groups_id)
        # No staff records exist for portal_tp — run the cron logic
        self.env["res.config.settings"].action_recompute_sports_followers_and_groups()
        self.portal_tp.invalidate_recordset(["groups_id"])
        self.assertNotIn(self.tp_group_portal, self.portal_tp.groups_id)
