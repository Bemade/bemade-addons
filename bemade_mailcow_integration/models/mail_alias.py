from odoo import models, fields, api, _
from odoo.exceptions import ValidationError

class MailAlias(models.Model):
    _inherit = 'mail.alias'

    mailcow_id = fields.One2many('mail.mailcow.alias', 'alias_id')


@api.model_create_multi
def create(self, vals_list):
    alias_list = super().create(vals_list)
    for alias in alias_list:
        if not alias.alias_name:
            continue
        alias_domain = self.env["ir.config_parameter"].sudo().get_param("mail.catchall.domain")
        catchall_alias = self.env["ir.config_parameter"].sudo().get_param("mail.catchall.alias")

        if alias_domain:
            mailcow_alias = self.env['mail.mailcow.alias'].search([('address', '=', alias.alias_name + '@' + alias_domain)])
            if mailcow_alias:
                mailcow_alias.write({'active': True})
            else:
                self.env['mail.mailcow.alias'].create({
                    'address': alias.alias_name + '@' + alias_domain,
                    'goto': catchall_alias + '@' + alias_domain,
                    'alias_id': alias.id,
                })
    return alias_list
