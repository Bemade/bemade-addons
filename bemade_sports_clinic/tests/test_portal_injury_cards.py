"""Tests for the portal injury cards refactor (task 536) + UX follow-ups.

Acceptance criteria:
- The player portal page (/my/player?player_id=X) renders each injury
  as a Bootstrap card (class portal-injury-card) instead of a table row.
- Cards carry a status badge whose colour matches the stage.
- The diagnosis title links to /my/injury/edit (no separate Edit
  button — that would duplicate the title link).
- Per-card action buttons are limited to Docs and Activities; the
  Activities button links to the activities LIST, not the create form.
- "Add Injury" lives inside the Injuries tab (header), not in the
  top action bar.
- A Notes tab is exposed for treatment professionals with an inline
  "Add Treatment Note" form and a list of existing notes (date desc).
- The empty-state ("No injuries recorded") still renders when the
  patient has no injuries.
"""

from odoo import Command
from odoo.tests import HttpCase, tagged


@tagged("-at_install", "post_install")
class TestPortalInjuryCards(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.team = cls.env["sports.team"].create({"name": "Cards Team"})

        cls.tp_partner = cls.env["res.partner"].create({
            "name": "Cards TP", "email": "cards.tp@example.com",
        })
        cls.env["sports.team.staff"].create({
            "team_id": cls.team.id,
            "partner_id": cls.tp_partner.id,
            "role": "therapist",
        })
        cls.tp_user = cls.env["res.users"].with_context(
            no_reset_password=True
        ).create({
            "partner_id": cls.tp_partner.id,
            "login": "cards.tp@example.com",
            "password": "cards-tp",
            "name": "Cards TP",
            "groups_id": [
                Command.link(cls.env.ref("base.group_portal").id),
                Command.link(cls.env.ref("bemade_sports_clinic.group_portal_treatment_professional").id),
            ],
        })

        cls.player_with_injuries = cls.env["sports.patient"].create({
            "first_name": "Has", "last_name": "Injuries",
            "team_ids": [(6, 0, [cls.team.id])],
        })
        cls.injury_active = cls.env["sports.patient.injury"].create({
            "patient_id": cls.player_with_injuries.id,
            "diagnosis": "Sprained ankle",
        })
        cls.injury_resolved = cls.env["sports.patient.injury"].create({
            "patient_id": cls.player_with_injuries.id,
            "diagnosis": "Healed bruise",
        })
        # The PatientInjury.create override forces stage='active' for
        # admins/TPs; flip the resolved one explicitly after create.
        cls.injury_resolved.write({"stage": "resolved"})

        cls.player_no_injuries = cls.env["sports.patient"].create({
            "first_name": "Clean", "last_name": "Slate",
            "team_ids": [(6, 0, [cls.team.id])],
        })

    def _open_player(self, player):
        self.authenticate("cards.tp@example.com", "cards-tp")
        return self.url_open(f"/my/player?player_id={player.id}")

    def test_injury_cards_rendered(self):
        resp = self._open_player(self.player_with_injuries)
        self.assertEqual(resp.status_code, 200)
        body = resp.content.decode("utf-8", errors="replace")
        # The cards container appears once; portal-injury-card class
        # appears once per injury (two here).
        self.assertIn("portal-injury-cards", body)
        # Container + 2 per-injury card classes = 3 occurrences.
        self.assertGreaterEqual(body.count("portal-injury-card"), 3)
        # Diagnoses appear in the rendered output.
        self.assertIn("Sprained ankle", body)
        self.assertIn("Healed bruise", body)

    def test_no_legacy_table_for_injuries(self):
        """The injuries tab should no longer render a portal_table —
        any remaining <table> elements on the page belong to other tabs
        (Patient Info, Documents, Treatment Notes)."""
        resp = self._open_player(self.player_with_injuries)
        body = resp.content.decode("utf-8", errors="replace")
        # The injuries tab markup should NOT contain the column headers
        # we removed.
        self.assertNotIn(">Injury</th>", body)
        self.assertNotIn(">External Notes</th>", body)

    def test_status_badge_classes_present(self):
        resp = self._open_player(self.player_with_injuries)
        body = resp.content.decode("utf-8", errors="replace")
        # Active injury → danger badge, resolved → success badge.
        self.assertIn("text-bg-danger", body)
        self.assertIn("text-bg-success", body)

    def test_empty_state_when_no_injuries(self):
        resp = self._open_player(self.player_no_injuries)
        body = resp.content.decode("utf-8", errors="replace")
        self.assertIn("No injuries recorded", body)
        self.assertNotIn("portal-injury-cards", body)

    def test_no_per_card_edit_button(self):
        """The diagnosis title is the edit link; a separate Edit button
        on the card would duplicate it."""
        resp = self._open_player(self.player_with_injuries)
        body = resp.content.decode("utf-8", errors="replace")
        # 'fa fa-edit me-1' was the per-card Edit button marker; should
        # be gone now. (The Edit Player button at the top still uses
        # 'fa fa-edit' without the me-1 spacing class.)
        self.assertNotIn("fa fa-edit me-1", body)

    def test_activities_button_links_to_list(self):
        resp = self._open_player(self.player_with_injuries)
        body = resp.content.decode("utf-8", errors="replace")
        self.assertIn(
            f"/my/injury/activities?injury_id={self.injury_active.id}",
            body,
        )
        # The old per-card "Add Activity" create-flow link should not
        # appear on the card any more.
        self.assertNotIn(
            f"/my/activity/create?model=sports.patient.injury&amp;res_id={self.injury_active.id}",
            body,
        )

    def test_add_injury_button_in_injuries_tab(self):
        resp = self._open_player(self.player_no_injuries)
        body = resp.content.decode("utf-8", errors="replace")
        # The Add Injury button should be inside the injuries tab pane,
        # which lives between id="injuries" and the next tab pane.
        injuries_idx = body.find('id="injuries"')
        next_tab_idx = body.find('id="patient-info"')
        self.assertGreater(injuries_idx, 0)
        self.assertGreater(next_tab_idx, injuries_idx)
        tab_html = body[injuries_idx:next_tab_idx]
        self.assertIn(
            f"/my/patient/injury/new?patient_id={self.player_no_injuries.id}",
            tab_html,
        )

    def test_notes_tab_present_with_form_and_list(self):
        # Pre-create a note to verify it shows in the list.
        self.env["sports.treatment.note"].create({
            "patient_id": self.player_with_injuries.id,
            "note": "Initial visit summary",
            "user_id": self.tp_user.id,
        })
        resp = self._open_player(self.player_with_injuries)
        body = resp.content.decode("utf-8", errors="replace")
        # Tab nav button + tab pane exist for TPs.
        self.assertIn('id="notes-tab"', body)
        self.assertIn('id="notes"', body)
        # Inline add-note form posts to the existing endpoint.
        self.assertIn('action="/my/injury/note/add"', body)
        # Existing note appears.
        self.assertIn("Initial visit summary", body)
