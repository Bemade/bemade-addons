from odoo.tests.common import TransactionCase, tagged


@tagged('-at_install', 'post_install')
class TestMailcow(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()

    def test_new_mail_alias(self):
        model_id = self.env['ir.model']._get('res.partner').id
        self.alias = self.env['mail.alias'].create({'alias_name': 'test', 'alias_model_id': model_id})
