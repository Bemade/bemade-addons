from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class MailcowAlias(models.Model):
    _name = 'mail.mailcow.alias'
    _description = 'Mailcow Alias'
    _inherit = ['mail.mailcow', 'mail.thread', 'mail.activity.mixin']
    _rec_name = 'address'

    address = fields.Char(string='Alias Address', required=True, tracking=True)
    goto = fields.Char(string='Alias Destination', required=True, tracking=True)
    active = fields.Boolean(string='Active', default=True, tracking=True)
    catchall = fields.Boolean(string='Catchall', default=False, tracking=True)
    alias_id = fields.Many2one(comodel_name='mail.alias', string='Alias')
    create_date_mailcow = fields.Datetime(string='Created on Mailcow', readonly=True)
    modify_date_mailcow = fields.Datetime(string='Modified on Mailcow', readonly=True)
    mc_id = fields.Integer(string='Mailcow ID', readonly=True)

    _sql_constraints = [
        ('address_unique', 'UNIQUE(address)', 'The alias address must be unique!'),
    ]

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

    def unlink(self):
        for record in self:
            endpoint = f"api/v1/delete/alias/{record.mc_id}"
            result = self.env['mail.mailcow'].api_request(endpoint, 'POST')
            if not result:
                raise ValidationError(_("Failed to delete alias on Mailcow server."))
        return super(MailcowAlias, self).unlink()

    def write(self, vals):
        for record in self:
            data = {
                "attr": {
                    "active": str(int(vals.get('active', record.active))),
                    "address": vals.get('address', record.address),
                    "goto": vals.get('goto', record.goto),
                    "private_comment": f"Modified by {self.env.user.name} on {fields.Datetime.now()}",
                    "public_comment": f"Alias modified in Odoo. Changes: {vals}",
                },
                "items": [record.mc_id]
            }
            result = self.env['mail.mailcow'].api_request('/api/v1/edit/alias', 'POST', data)
            if not result:
                raise ValidationError(_("Failed to update alias on Mailcow server."))

        return super(MailcowAlias, self).write(vals)

    @api.model
    def sync_aliases(self):
        """
        Synchronize the list of aliases from Mailcow server with Odoo.
        For each alias fetched from Mailcow server, it tries to find a matching record
        in Odoo. If it doesn't exist, it creates a new record.
        """
        endpoint = '/api/v1/get/alias/all'
        mailcow_aliases = self.api_request(endpoint)

        if not mailcow_aliases:
            return

        for mc_alias in mailcow_aliases:
            domain = mc_alias['domain']

            alias_domain = self.env['ir.config_parameter'].sudo().get_param('mail.catchall.domain')
            if domain == alias_domain:
                alias = self.search([('mc_id', '=', mc_alias['id'])], limit=1)
                if not alias:
                    self.create({
                        'address': mc_alias['address'],
                        'active': bool(mc_alias['active']),
                        'goto': mc_alias['goto'],
                        'mc_id': mc_alias['id'],
                        'create_date_mailcow': mc_alias['created'],
                        'modify_date_mailcow': mc_alias['modified'],
                    })
                else:
                    alias.write({
                        'address': mc_alias['address'],
                        'active': bool(mc_alias['active']),
                        'goto': mc_alias['goto'],
                        'create_date_mailcow': mc_alias['created'],
                        'modify_date_mailcow': mc_alias['modified'],
                    })
