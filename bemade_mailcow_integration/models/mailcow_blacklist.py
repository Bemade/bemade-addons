# -*- coding: utf-8 -*-

from odoo import models, fields, api
import logging

_logger = logging.getLogger(__name__)

class MailcowBlacklist(models.Model):
    _name = 'mail.mailcow.blacklist'
    _description = 'Mailcow Blacklist'
    _inherit = ['mail.mailcow', 'mail.thread', 'mail.activity.mixin']

    email = fields.Char(string='Email', required=True, tracking=True)
    mc_id = fields.Integer(string='Mailcow ID', required=True, tracking=True)

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

    @api.model
    def sync_blacklist(self):
        """
        Function to sync Mailcow blacklist with Odoo's blacklist. It fetches the list from Mailcow
        and updates Odoo's blacklist accordingly.

        Returns:
            bool: True if the sync is successful, False otherwise
        """
        params = self.env['ir.config_parameter'].sudo()
        domain = params.get_param('mail.catchall.domain')
        endpoint = f'/api/v1/get/policy_bl_domain/{domain}'
        try:
            response = self.api_request(endpoint, 'GET')
            if response:
                for item in response:
                    existing = self.search([('mc_id', '=', item['prefid'])], limit=1)
                    if existing:
                        if existing.email != item['value']:
                            existing.write({'email': item['valuw']})
                    else:
                        self.create({
                            'email': item['value'],
                            'mc_id': item['prefid'],
                        })
            return True
        except Exception as e:
            _logger.error('An error occurred while syncing blacklist: %s', str(e))
            return False
