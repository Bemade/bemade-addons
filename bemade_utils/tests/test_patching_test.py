from odoo.tests import TransactionCase
from addons.bemade_utils.tools.test import patch_test


class TestA(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

    def test_method_a(self):
        self.assertFalse(True)


class TestB(TransactionCase):
    @patch_test(TestA.test_method_a)
    def test_redefining_test(self):
        self.assertTrue(True)
