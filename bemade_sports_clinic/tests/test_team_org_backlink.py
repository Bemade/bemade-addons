# Acceptance criteria:
# - Creating a sports.team from the organization form view's "Teams" tab (owned_team_ids)
#   must set parent_id to the organization automatically, via default_parent_id context.
# - The team must appear in org.owned_team_ids after creation.

from odoo.tests import TransactionCase, tagged
from odoo.tests.common import Form


@tagged("-at_install", "post_install")
class TestTeamOrgBacklink(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.org = cls.env["res.partner"].create({"name": "Test Org", "is_company": True})

    def test_create_team_from_org_form_sets_parent_id(self):
        """Simulates clicking 'New' on owned_team_ids from the org form view.

        The One2many widget must inject default_parent_id so the team's
        parent_id is set to the organization without the user explicitly choosing it.
        """
        # Simulate the context the One2many widget injects when opening a new-record dialog
        team_form = Form(
            self.env["sports.team"].with_context(default_parent_id=self.org.id)
        )
        team_form.name = "Juniors"
        team = team_form.save()

        self.assertEqual(
            team.parent_id,
            self.org,
            "Team parent_id should be set to the organization via default_parent_id context",
        )
        self.assertIn(
            team,
            self.org.owned_team_ids,
            "Newly created team should appear in org.owned_team_ids",
        )

    def test_owned_team_ids_field_passes_default_parent_id(self):
        """The owned_team_ids field on the partner form must have context={'default_parent_id': id}
        so Odoo's One2many widget injects the correct default when the user clicks New.

        This test verifies the view XML has the context attribute set.
        """
        view = self.env.ref(
            "bemade_sports_clinic.res_partner_view_form_sports_teams"
        )
        self.assertIn(
            "default_parent_id",
            view.arch,
            "owned_team_ids field must include context with default_parent_id "
            "so new teams created from the org form are linked automatically",
        )
