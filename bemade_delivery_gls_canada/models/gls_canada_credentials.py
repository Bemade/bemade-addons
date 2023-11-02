from odoo import models, fields, api, _


class GLSCanadaAccount(models.Model):
    _name = 'gls.canada.account'
    _inherit = 'delivery.account'
    _description = 'GLS Canada Account'

    account_credentials = fields.Many2one('gls.canada.credentials', string='Login Credentials')
    account_type = fields.Selection([
        ('Parcel', 'Parcel'),
        ('Freight', 'Freight'),
        ('Distribution', 'Distribution'),
        ('Logistics', 'Logistics'),
    ],
        default='Parcel')


class GLSCanadaCredentials(models.Model):
    _name = 'gls.canada.credentials'
    _inherit = 'delivery.account.credentials'
    _description = 'Login credentials for GLS Canada'

    production_url = fields.Char('Production URL', default='https://smart4i.dicom.com/v1')
    test_url = fields.Char('Test URL', default='https://sandbox-smart4i.dicom.com/v1')
