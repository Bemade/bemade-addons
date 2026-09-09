from odoo.tests import HttpCase, tagged
from odoo import Command
from odoo.http import Request


@tagged("-at_install", "post_install")
class TestPortalInjuryAutoAssign(HttpCase):
    """Validate therapist auto-assignment during portal injury creation.

    Scenarios:
    - Treatment Professional creates injury with an explicit checkbox selection:
      assignment is exactly the selected TPs (no auto-assign of team therapists
      or actor — explicit selection is exclusive per controller contract).
    - Coach creates injury: assigned = team therapists only (no coach user).
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env

        # Base org and team
        cls.org = env['res.partner'].create({
            'name': 'AutoAssign Org',
            'is_company': True,
        })
        cls.team = env['sports.team'].create({
            'name': 'AutoAssign Team',
            'parent_id': cls.org.id,
        })

        # Patient
        cls.patient = env['sports.patient'].create({
            'first_name': 'Injury',
            'last_name': 'Subject',
            'date_of_birth': '2006-06-06',
            'team_ids': [(4, cls.team.id)],
        })

        # Users: TP1 (actor), TP2 (select extra), Coach (actor)
        base_portal = env.ref('base.group_portal')
        tp_group_portal = env.ref('bemade_sports_clinic.group_portal_treatment_professional')
        coach_group = env.ref('bemade_sports_clinic.group_portal_team_coach')

        # Team therapists via team staff: map partner to user(s)
        cls.tp1_partner = env['res.partner'].create({'name': 'TP1', 'email': 'tp1@example.com'})
        cls.tp1_user = env['res.users'].with_context(no_reset_password=True).create({
            'partner_id': cls.tp1_partner.id,
            'login': 'tp1@example.com',
            'password': 'tp1',
            'name': 'TP1',
            'groups_id': [Command.link(base_portal.id), Command.link(tp_group_portal.id)],
        })
        env['sports.team.staff'].create({
            'team_id': cls.team.id,
            'partner_id': cls.tp1_partner.id,
            'role': 'therapist',
        })

        # Second therapist, also part of team via staff
        cls.tp2_partner = env['res.partner'].create({'name': 'TP2', 'email': 'tp2@example.com'})
        cls.tp2_user = env['res.users'].with_context(no_reset_password=True).create({
            'partner_id': cls.tp2_partner.id,
            'login': 'tp2@example.com',
            'password': 'tp2',
            'name': 'TP2',
            'groups_id': [Command.link(base_portal.id), Command.link(tp_group_portal.id)],
        })
        env['sports.team.staff'].create({
            'team_id': cls.team.id,
            'partner_id': cls.tp2_partner.id,
            'role': 'head_therapist',
        })

        # Additional TP3 not in team; used for explicit selection by TP1
        cls.tp3_partner = env['res.partner'].create({'name': 'TP3', 'email': 'tp3@example.com'})
        cls.tp3_user = env['res.users'].with_context(no_reset_password=True).create({
            'partner_id': cls.tp3_partner.id,
            'login': 'tp3@example.com',
            'password': 'tp3',
            'name': 'TP3',
            'groups_id': [Command.link(base_portal.id), Command.link(tp_group_portal.id)],
        })

        # Coach user
        cls.coach_partner = env['res.partner'].create({'name': 'Coach', 'email': 'coach@example.com'})
        cls.coach_user = env['res.users'].with_context(no_reset_password=True).create({
            'partner_id': cls.coach_partner.id,
            'login': 'coach@example.com',
            'password': 'coach',
            'name': 'Coach',
            'groups_id': [Command.link(base_portal.id), Command.link(coach_group.id)],
        })
        # Add coach as staff for access (role coach)
        env['sports.team.staff'].create({
            'team_id': cls.team.id,
            'partner_id': cls.coach_partner.id,
            'role': 'coach',
        })

    def _latest_injury(self):
        return self.env['sports.patient.injury'].search([('patient_id', '=', self.patient.id)], order='id desc', limit=1)

    def test_autoassign_when_tp_creates_injury(self):
        # TP1 logs in and creates injury selecting TP3 additionally, team set
        self.authenticate('tp1@example.com', 'tp1')
        data = {
            'csrf_token': Request.csrf_token(self),
            'patient_id': str(self.patient.id),
            'team_id': str(self.team.id),
            'diagnosis': 'Hamstring strain',
            # Multi-select checkboxes come as repeated keys treatment_professional_ids[]
            'treatment_professional_ids[]': [str(self.tp3_user.id)],
        }
        resp = self.url_open('/my/patient/injury/create', data=data, timeout=30)
        self.assertEqual(resp.status_code, 200)

        injury = self._latest_injury()
        self.assertTrue(injury, 'Injury should be created')
        assigned = set(injury.treatment_professional_ids.ids)
        expected = {self.tp3_user.id}
        self.assertEqual(assigned, expected, f"Explicit selection should be exclusive; assigned={assigned}, expected={expected}")

    def test_autoassign_when_coach_creates_injury(self):
        # Coach logs in and creates injury; should auto-assign only team therapists (TP1, TP2), not coach
        self.authenticate('coach@example.com', 'coach')
        data = {
            'csrf_token': Request.csrf_token(self),
            'patient_id': str(self.patient.id),
            'team_id': str(self.team.id),
            'diagnosis': 'Ankle sprain',
        }
        resp = self.url_open('/my/patient/injury/create', data=data, timeout=30)
        self.assertEqual(resp.status_code, 200)

        injury = self._latest_injury()
        self.assertTrue(injury, 'Injury should be created by coach')
        assigned = set(injury.treatment_professional_ids.ids)
        expected_team = {self.tp1_user.id, self.tp2_user.id}
        self.assertEqual(assigned, expected_team, f"Coach flow should assign only team therapists {expected_team}, got {assigned}")
