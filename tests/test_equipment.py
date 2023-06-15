from odoo.tests.common import HttpCase, tagged
from odoo.tools import mute_logger
from odoo.exceptions import MissingError
from odoo import Command
from psycopg2.errors import ForeignKeyViolation
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
            'state_id': cls.env['res.country.state'].search([('name','ilike','Quebec%')]),
            'country_id': cls.env['res.country'].search([('name','=','Canada')])
        })

        cls.partner_contact = cls.env['res.partner'].create({
            'name': 'Site Contact',
            'company_type': 'person',
            'parent_id': cls.partner_company.id,
        })

        cls.equipment = cls.env['bemade_fsm.equipment'].create({
            'name': 'Test Equipment 1',
        })