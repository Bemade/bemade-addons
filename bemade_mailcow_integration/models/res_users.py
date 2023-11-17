from odoo import models, fields, api

class ResUsers(models.Model):
    _inherit = 'res.users'

    # def _compute_create_mailcow_mailbox(self):
    #     params = self.env['ir.config_parameter'].sudo()
    #     can_create = params.get_param('mailcow.create_mailbox')
    #     return can_create

    mailcow_mailbox = fields.Boolean(string='Mailcow Mailbox', default=False)

    # can_create_mailcow_mailbox = fields.Boolean(
    #     string='Create Mailcow Mailbox',
    #     compute=_compute_create_mailcow_mailbox
    # )

    mailcow_auto_create = fields.Boolean(compute='_compute_mailcow_auto_create', string='Create Mailbox in Mailcow')


    def _compute_mailcow_auto_create(self):
        for rec in self:
            config = self.env['ir.config_parameter'].sudo()
            get_mailcow_auto_create = config.get_param('mailcow_auto_create', False)
            rec.mailcow_auto_create = get_mailcow_auto_create


    @api.model_create_multi
    def create(self, vals_list):
        res_list = super().create(vals_list)

        for res in res_list:
            if res.mailcow_mailbox:
                self.env['mail.mailcow.mailbox'].create_mailbox_for_user(res)

        return res_list

