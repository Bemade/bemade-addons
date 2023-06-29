# -*- coding: utf-8 -*-

from odoo import models, fields, api, exceptions
import requests
import logging

_logger = logging.getLogger(__name__)

class MailMailcow(models.AbstractModel):
    _name = 'mail.mailcow'
    _description = 'Mailcow API'

    def get_credentials(self):
        params = self.env['ir.config_parameter'].sudo()
        return {
            'base_url': params.get_param('mailcow.base_url'),
            'api_key': params.get_param('mailcow.api_key'),
        }

    def api_request(self, endpoint, method='GET', data=None):
        creds = self.get_credentials()
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
