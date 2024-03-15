from odoo.tests.common import HttpCase, tagged
from .test_bemade_fsm_common import BemadeFSMBaseTest
from odoo import Command
from odoo.exceptions import MissingError


@tagged("-at_install", "post_install")
class TestEquipment(BemadeFSMBaseTest):
    def test_crud(self):
        partner_company = self._generate_partner()
        partner_contact = self._generate_partner('Site Contact', 'person', partner_company)
        equipment = self._generate_equipment('Test Equipment 1', partner_company)

        # Just make sure the basic ORM stuff is OK
        self.assertTrue(equipment in partner_company.equipment_ids)
        self.assertTrue(len(partner_company.equipment_ids) == 1)

        # Delete should cascade
        partner_company.write({'equipment_ids': [Command.set([])]})
        with self.assertRaises(MissingError):
            equipment.name

    def test_compute_complete_name_when_name_blank(self):
        equipment = self._generate_equipment(name=False)
        complete_name = equipment.complete_name
