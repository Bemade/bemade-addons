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


@tagged('-at_install', 'post_install', 'slow')
class TestEquipmentTours(HttpCase, BemadeFSMBaseTest):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        partner = cls._generate_partner("Test Partner")
        cls._generate_partner('Site Contact', 'person', parent=partner)
        cls._generate_equipment(name='Test Equipment 1', partner=partner)
        cls.user = cls._generate_project_manager_user("Mister PM", 'misterpm')

    def test_equipment_base_tour(self):
        self.start_tour('/web', 'equipment_base_tour',
                        login=self.user.login, )

    def test_equipment_sale_order_tour(self):
        self.start_tour('/web', 'equipment_sale_order_tour', login=self.user.login)
