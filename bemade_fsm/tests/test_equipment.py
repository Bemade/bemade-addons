from odoo.tests.common import HttpCase, tagged
from .test_bemade_fsm_common import BemadeFSMBaseTest
from odoo import Command
from odoo.exceptions import MissingError


@tagged("-at_install", "post_install")
class TestEquipment(BemadeFSMBaseTest):
    def test_crud(self):
        self.partner_company = self._generate_partner()
        self.partner_contact = self._generate_partner('Site Contact', 'person', self.partner_company)
        self.equipment = self._generate_equipment('Test Equipment 1', self.partner_company)

        # Just make sure the basic ORM stuff is OK
        self.assertTrue(self.equipment in self.partner_company.equipment_ids)
        self.assertTrue(len(self.partner_company.equipment_ids) == 1)

        # Delete should cascade
        self.partner_company.write({'equipment_ids': [Command.set([])]})
        with self.assertRaises(MissingError):
            self.equipment.name


@tagged('-at_install', 'post_install', 'slow')
class TestEquipmentTours(HttpCase, BemadeFSMBaseTest):

    @classmethod
    def setUpClass(cls):
        cls._generate_partner()
        cls._generate_partner('Site Contact', 'person', cls.partner_company)
        cls._generate_equipment('Test Equipment 1', cls.partner_company)

    def test_equipment_base_tour(self):
        self.start_tour('/web', 'equipment_base_tour',
                        login=self.user.login, )

    def test_equipment_sale_order_tour(self):
        self.start_tour('/web', 'equipment_sale_order_tour', login=self.user.login)
