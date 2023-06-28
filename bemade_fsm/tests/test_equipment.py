from odoo.tests.common import HttpCase, tagged
from .test_bemade_fsm_common import FSMManagerUserTransactionCase
from odoo import Command
from odoo.exceptions import MissingError


@tagged("-at_install", "post_install")
class TestEquipmentCommon(FSMManagerUserTransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # Set up the test partner
        cls.partner_company = cls.env['res.partner'].create({
            'name': 'Test Partner Company',
            'company_type': 'company',
            'street': '123 Street St.',
            'city': 'Montreal',
            'state_id': cls.env['res.country.state'].search([('name', 'ilike', 'Quebec%')]).id,
            'country_id': cls.env['res.country'].search([('name', '=', 'Canada')]).id
        })

        cls.partner_contact = cls.env['res.partner'].create({
            'name': 'Site Contact',
            'company_type': 'person',
            'parent_id': cls.partner_company.id,
        })

        cls.equipment = cls.env['bemade_fsm.equipment'].create({
            'name': 'Test Equipment 1',
            'partner_location_id': cls.partner_company.id,
        })


@tagged('-at_install', 'post_install')
class TestEquipmentBase(TestEquipmentCommon):

    def test_crd(self):
        # Just make sure the basic ORM stuff is OK
        self.assertTrue(self.equipment in self.partner_company.equipment_ids)
        self.assertTrue(len(self.partner_company.equipment_ids) == 1)
        self.partner_company.write({'equipment_ids': [Command.set([])]})
        # Delete should cascade
        with self.assertRaises(MissingError):
            self.equipment.name


@tagged('-at_install', 'post_install')
class TestEquipmentTours(HttpCase, TestEquipmentCommon):

    def test_equipment_base_tour(self):
        self.start_tour('/web', 'equipment_base_tour',
                        login=self.user.login, )

    def test_equipment_sale_order_tour(self):
        self.start_tour('/web', 'equipment_sale_order_tour', login=self.user.login)
