from odoo import models, fields, api, _


class DeliveryAccount(models.Model):
    """
    A delivery account is a set of credentials that can be used to access a delivery service. It can be as simple as
    an account number to use for a collect shipment and as complex as the full set of credentials required to make API
    calls to book shipments with a given carrier. This class is meant to be extended by other modules via classical
    inheritance to provide credentials that can be used for various partners, specially calibrated to different
    delivery carrier types.

    If the account should use credentials information specific to a given delivery method (carrier), then the
    delivery.account.credentials model should be extended and the extended model should be used in the
    account_credentials field of the extended delivery.account model. Models that extend delivery.account should be
    set to _auto = False
    """
    _name = 'delivery.account'
    _description = 'Delivery Account'
    _rec_name = 'account_number'

    @api.model
    def _get_carrier_selection(self):
        return self.env['delivery.carrier'].fields_get(['delivery_type'])['delivery_type']['selection']

    def _get_account_type_domain(self):
        if self.delivery_type:
            return [('delivery_type', '=', self.delivery_type)]
        else:
            return []

    delivery_type = fields.Selection(selection='_get_carrier_selection', string='Applicable Carrier')
    account_number = fields.Char()
    account_credentials_id = fields.Many2one('delivery.account.credentials', string='Login Credentials')
    partner_ids = fields.Many2many(comodel_name='res.partner', string='Partners',
                                   relation='delivery_account_partner_rel',
                                   column1='account_id', column2='partner_id',
                                   help="Partners who can use this account.")
    account_type_id = fields.Many2one('delivery.account.type', string='Account Type', domain=_get_account_type_domain)


class DeliveryAccountCredentials(models.Model):
    """
    Login credentials for a given account. This model is meant to be extended using classic inheritance. Suggested usage
    is to extend the model and set the default production_url and test_url values to simplify the UI for the user. The
    extended model should be used in the account_credentials field of the DeliveryAccount model.
    """
    _name = 'delivery.account.credentials'
    _description = 'Delivery Account Login Credentials'
    _rec_name = 'username'

    username = fields.Char()
    password = fields.Char()
    production_url = fields.Char(string='Production URL')
    test_url = fields.Char(string='Test URL')
    delivery_account_id = fields.One2many(comodel_name='delivery.account', inverse_name='account_credentials_id', )


class DeliveryAccountType(models.Model):
    _name = 'delivery.account.type'
    _description = 'Delivery Account Type'

    name = fields.Char(required=True)
    technical_name = fields.Char(help="The technical name used by the carrier to identify the account type.",
                                 required=True)
    carrier_id = fields.Many2one('delivery.carrier', string='Carrier', required=True)
    delivery_type = fields.Selection(related='carrier_id.delivery_type', string='Delivery Type', readonly=True)
