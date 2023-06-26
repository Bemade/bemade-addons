from odoo.tests import TransactionCase, HttpCase, tagged
from odoo import Command


class TestCustomAppOrder(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        user_group = cls.env.ref('base.group_user')

        Users = cls.env['res.users'].with_context({'no_reset_password': True})
        Employees = cls.env['hr.employee']

        user_partner = cls.env['res.partner'].create({
            'name': 'User Partner',
        })
        cls.user = Users.create({
            'name': 'Regular User',
            'login': 'reguser',
            'partner_id': user_partner.id,
            'password': 'reguser',
            'email': 'regular_user@test.co',
            'groups_id': [(6, 0, [user_group.id])]
        })
        user_employee = Employees.create({
            'name': 'Regular User',
            'address_home_id': user_partner.id,
            'user_id': cls.user.id,
        })


@tagged('-at_install', 'post_install')
class TestCustomAppOrderTours(HttpCase, TestCustomAppOrder):

    def test_as_regular_user(self):
        self.start_tour('/web', 'custom_app_order_tour', login='reguser')
