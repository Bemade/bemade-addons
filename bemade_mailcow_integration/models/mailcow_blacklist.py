# -*- coding: utf-8 -*-

from odoo import models, fields, api
import logging
import json

_logger = logging.getLogger(__name__)


class MailcowBlacklist(models.Model):
    _name = 'mail.mailcow.blacklist'
    _description = 'Mailcow Blacklist'
    _inherit = ['mail.mailcow', 'mail.thread', 'mail.activity.mixin']

    email = fields.Char(string='Email', required=True, tracking=True)
    mc_id = fields.Integer(string='Mailcow ID', required=True, tracking=True)

    @api.model_create_multi
    def create(self, vals_list):
        alias_list = super().create(vals_list)
        for alias in alias_list:

            if 'mc_id' not in alias:
                data = {
                    "active": bool(alias.active),
                    "address": alias.address,
                    "catchall": bool(alias.catchall),
                    "goto": alias.goto,
                    "private_comment": f"Created by {self.env.user.name} on {fields.Datetime.now()}",
                    "public_comment": "Alias created in Odoo"
                }
                result = self.env['mail.mailcow'].api_request('/api/v1/add/alias', 'POST', data)
                if not result:
                    #pass
                    raise ValidationError("Failed to create alias on Mailcow server.")

        return alias_list

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
        endpoint = '/api/v1/delete/domain-policy'
        for record in self:
            data = json.dumps(record.mc_id)
            self.api_request(endpoint, 'POST', data)
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
