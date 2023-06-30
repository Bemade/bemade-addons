# -*- coding: utf-8 -*-

from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)

class MailcowBlacklist(models.Model):
    _name = 'mail.mailcow.blacklist'
    _description = 'Mailcow Blacklist'
    _inherit = ['mail.mailcow', 'mail.thread', 'mail.activity.mixin']

    email = fields.Char(string='Email', required=True, tracking=True)
    prefid = fields.Integer(string='Mailcow ID', required=True, tracking=True)

    @api.model
    def create(self, vals):
        """
        Overridden create method to add the new blacklist entry to the Mailcow server.
        """
        res = super().create(vals)
        domain = self.env['ir.config_parameter'].sudo().get_param('mail.catchall.domain')

        endpoint_add = '/api/v1/add/domain-policy'
        endpoint_get_bl = f"/api/v1/get/policy_bl_domain/{domain}"
        data = {
            'domain': domain,
            'object_from': res.email,
            'object_list': 'bl'
        }
        res.api_request(endpoint_add, 'POST', data)
        _logger.info(f'Added {vals["email"]} to Mailcow blacklist')

        res.api_request(endpoint_get_bl, 'GET', None)

        return res

    def write(self, vals):
        """
        Overridden write method to update the blacklist entry on the Mailcow server.
        """
        old_email = self.email
        res = super().write(vals)
        if 'email' in vals:
            delete_endpoint = '/api/v1/delete/domain-policy'
            add_endpoint = '/api/v1/add/domain-policy'
            delete_data = {
                'items': [old_email]
            }
            add_data = {
                'items': [vals['email']]
            }
            self.api_request(delete_endpoint, 'POST', delete_data)
            self.api_request(add_endpoint, 'POST', add_data)
            _logger.info(f'Updated {old_email} to {vals["email"]} in Mailcow blacklist')
        return res

    def unlink(self):
        """
        Overridden unlink method to remove the blacklist entry from the Mailcow server.
        """
        for record in self:
            endpoint = '/api/v1/delete/blacklist'
            data = {
                'items': [record.email]
            }
            record.api_request(endpoint, 'POST', data)
            _logger.info(f'Removed {record.email} from Mailcow blacklist')
        return super().unlink()
