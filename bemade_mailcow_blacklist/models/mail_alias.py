from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class MailAlias(models.Model):
    _inherit = 'mail.alias'

    mailcow_id = fields.One2many('mail.mailcow.alias', 'alias_id')

    def create(self, vals):
        alias = super(MailAlias, self).create(vals)
        mailcow_alias = self.env['mail.mailcow.alias'].search([('address', '=', alias.alias_name + '@' + alias.alias_domain)])
        if mailcow_alias:
            mailcow_alias.write({'active': True})
        else:
            self.env['mail.mailcow.alias'].create({
                'address': alias.alias_name + '@' + alias.alias_domain,
                'goto': alias.alias_defaults.get('email_from', False),
                'alias_id': alias.id,
            })
        return alias
