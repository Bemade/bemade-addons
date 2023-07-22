# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
import requests
import logging
from odoo.exceptions import ValidationError


_logger = logging.getLogger(__name__)

class MailMailcow(models.AbstractModel):
    _name = 'mail.mailcow'
    _description = 'Mailcow API'

    @property
    def get_credentials(self):
        params = self.env['ir.config_parameter'].sudo()

        base_url = params.get_param('mailcow.base_url')
        api_key = params.get_param('mailcow.api_key')

        if not base_url or not api_key:
            _logger.error('No API key or base URL is set in the system parameters')
            raise ValidationError(_("No API key or base URL is set in the system parameters.  Please set one and try again."))
            # return False
        else:
            return {
                'base_url': base_url,
                'api_key': api_key
            }

    def api_request(self, endpoint, method='GET', data=None):
        creds = self.get_credentials
        if not creds:
            return False
        url = creds['base_url'] + endpoint
        headers = {
            'accept': 'application/json',
            'X-API-Key': creds['api_key'],
            'Content-Type': 'application/json',
        }

        try:
            if method == 'GET':
                response = requests.get(url, headers=headers)
            elif method == 'POST':
                response = requests.post(url, headers=headers, json=data)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers)
            elif method == 'PUT':
                response = requests.put(url, headers=headers, json=data)

            response.raise_for_status()

        except requests.exceptions.HTTPError as error:
            _logger.error('HTTP error occurred: %s', error)
            return False
        except Exception as error:
            _logger.error('An error occurred: %s', error)
            return False

        return response.json()
