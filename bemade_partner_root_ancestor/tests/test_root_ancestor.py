from odoo.tests.common import TransactionCase, tagged
from odoo import Command


class TestPartnerRootAncestor(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        partner = cls.env['res.partner']
        cls.common_ancestor = partner.create({
            'name': 'Parnter name',
            'company_type': 'company',
        })
        cls.first_child = partner.create({
            'name': 'Child name',
            'company_type': 'company',
            'parent_id': cls.common_ancestor.id,
        })
        cls.second_child = partner.create({
            'name': 'Child name',
            'company_type': 'company',
            'parent_id': cls.common_ancestor.id,
        })
        cls.first_grandchild = partner.create({
            'name': 'Grandchild name',
            'company_type': 'person',
            'parent_id': cls.first_child.id,
        })
        cls.second_grandchild = partner.create({
            'name': 'Grandchild name',
            'company_type': 'person',
            'parent_id': cls.second_child.id,
        })
        cls.unrelated_partner = partner.create({
            'name': 'Unrelated partner',
        })
        cls.relatives = [cls.common_ancestor, cls.first_child, cls.second_child, cls.first_grandchild,
                     cls.second_grandchild]

    @tagged('-at_install', 'post_install')
    def testBaseCase(self):
        for r1 in self.relatives:
            self.assertFalse(r1.root_ancestor == self.unrelated_partner)
            for r2 in self.relatives:
                self.assertTrue(r1.root_ancestor == r2.root_ancestor)

    @tagged('-at_install', 'post_install')
    def testNewRelative(self):
        new_relative = self.env['res.partner'].create({
            'name': 'Whatever',
            'company_type': 'person',
            'parent_id': self.second_grandchild.id,
        })
        for r1 in self.relatives:
            self.assertTrue(r1.root_ancestor == new_relative.root_ancestor)