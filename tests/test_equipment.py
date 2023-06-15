from odoo.tests.common import HttpCase, tagged
from .test_bemade_fsm_common import FSMManagerUserTransactionCase

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
            'state_id': cls.env['res.country.state'].search([('name','ilike','Quebec%')]).id,
            'country_id': cls.env['res.country'].search([('name','=','Canada')]).id
        })

        cls.partner_contact = cls.env['res.partner'].create({
            'name': 'Site Contact',
            'company_type': 'person',
            'parent_id': cls.partner_company.id,
        })

        cls.equipment = cls.env['bemade_fsm.equipment'].create({
            'name': 'Test Equipment 1',
        })


@tagged('-at_install', 'post_install')
class TestEquipmentTour(HttpCase, TestEquipmentCommon):

    def test_equipment_tour(self):
        self.start_tour('/web', 'task_equipment_tour',
                        login=self.user.login, )
