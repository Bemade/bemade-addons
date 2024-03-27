from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging
import secrets
import string

_logger = logging.getLogger(__name__)

class MailcowMailbox(models.Model):
    _name = 'mail.mailcow.mailbox'
    _inherit = ['mail.mailcow', 'mail.thread', 'mail.activity.mixin']
    _description = 'Mailcow Mailbox'

    def _default_domain(self):
        return self.env["ir.config_parameter"].sudo().get_param("mail.catchall.domain")

    name = fields.Char(tracking=True)
    address = fields.Char(compute='_compute_address', store=True, readonly=True, tracking=True)
    local_part = fields.Char(required=True, tracking=True)
    domain = fields.Char(required=True, tracking=True, default=_default_domain)
    active = fields.Boolean(default=True, tracking=True)
    user_id = fields.Many2one('res.users', ondelete='cascade', tracking=True)
    password = fields.Char(readonly=True, tracking=True)

    @api.depends('local_part', 'domain')
    def _compute_address(self):
        for record in self:
            record.address = f"{record.local_part}@{record.domain}"

    @api.model
    def sync_mailboxes(self):
        """
        Synchronize Mailcow mailboxes with Odoo
        """
        endpoint = '/api/v1/get/mailbox/all'
        data = self.api_request(endpoint)
        domain = self.env['ir.config_parameter'].sudo().get_param('mail.catchall.domain')
        if data:
            for item in data:
                if item['domain'] == domain:
                    mailbox = self.env['mail.mailcow.mailbox'].search([('address', '=', f"{item['local_part']}@{item['domain']}")])
                    if not mailbox:
                        self.create({
                            'name': item['name'],
                            'local_part': item['local_part'],
                            'domain': item['domain'],
                            'active': item['active'],
                        })

    @api.model_create_multi
    def create(self, vals_list):
        """
        Overridden create method to add a new mailbox entry on the Mailcow server for each user created in Odoo.
        """

        res = self.env['mail.mailcow.mailbox']

        for vals in vals_list:
            password = secrets.token_hex(16)
            vals['password'] = password

            # Check if email exists on Mailcow
            endpoint = f"/api/v1/get/mailbox/{vals['local_part']}@{vals['domain']}"
            response = self.api_request(endpoint)

            if not response:
                # If email does not exist on Mailcow, create it
                endpoint = '/api/v1/add/mailbox'
                data = {
                    'local_part': vals['local_part'],
                    'domain': vals['domain'],
                    'name': vals['name'],
                    'password': password,
                    'password2': password,
                    'quota': "3072",
                    'active': "1",
                    'force_pw_update': "0",
                    'tls_enforce_in': "0",
                    'tls_enforce_out': "0",
                }
                self.api_request(endpoint, method='POST', data=data)
                _logger.info(f"Mailbox {vals['local_part']}@{vals['domain']} has been created on Mailcow server")

            res |= super().create(vals)
        return res

    def write(self, vals):
        """
        Override the write function to update a Mailcow mailbox whenever a user is updated in Odoo.
        """
        if 'active' in vals or 'local_part' in vals or 'domain' in vals:
            endpoint = f'/api/v1/edit/mailbox/{self.address}'
            data = {
                'items': [self.address],
                'attr': {
                    'active': '1' if vals.get('active', self.active) else '0',
                    'local_part': vals.get('local_part', self.local_part),
                    'domain': vals.get('domain', self.domain),
                }
            }
            self.api_request(endpoint, method='POST', data=data)
            _logger.info(f'Mailbox {self.address} has been updated on Mailcow server')

        return super().write(vals)

    def unlink(self):
        """
        Override the unlink function to delete a Mailcow mailbox whenever a user is deleted in Odoo.
        """

        for mailbox in self:
            data = {
                'username': mailbox.address
            }

            endpoint = f'/api/v1/delete/mailbox'
            mailbox.api_request(endpoint, method='POST', data=data)
            _logger.info(f'Mailbox {mailbox.address} has been deleted on Mailcow server')

        return super().unlink()

    def create_mailbox_for_user(self, user):
        """
        Function to create a Mailcow mailbox for a new Odoo user.

        Parameters:
            user (res.users): The newly created Odoo user

        Returns:
            mail.mailcow.mailbox: The newly created Mailcow mailbox
        """
        data = {
            'local_part': user.login.split('@')[0],
            'domain': user.login.split('@')[1],
            'name': user.name,
            'password': user.password,
        }
        endpoint = '/api/v1/add/mailbox'
        self.api_request(endpoint, method='POST', data=data)
        _logger.info(f'Mailbox for user {user.login} has been created on Mailcow server')

        pw_bundle = self.env['password.bundle'].search([('name', '=', user.name)])
        self.env['password.key'].create_mailbox_for_user(user)

        return self.create({
            'address': user.login,
            'user_id': user.id,
        })