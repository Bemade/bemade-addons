from odoo import models, exceptions, _

class Mail(models.Model):
    _inherit = 'mail.mail'

    def send(self, auto_commit=False, raise_exception=False):
        for mail in self:
            if mail.email_to:
                partner = self.env['res.partner'].search([('email', '=', mail.email_to)], limit=1)
                if partner and not partner.email_validated:
                    model = self.env[mail.model].browse(mail.res_id)
                    model.message_post(body=_('Cannot send email because the recipient\'s email address is not validated.'))
                    if raise_exception:
                        raise exceptions.UserError(_('Cannot send email because the recipient\'s email address is not validated.'))
                    continue
        return super().send(auto_commit=auto_commit, raise_exception=raise_exception)
