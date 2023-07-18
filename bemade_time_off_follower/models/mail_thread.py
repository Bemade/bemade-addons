from odoo import models, api

class MailThread(models.AbstractModel):
    _inherit = 'mail.thread'

    @api.returns('mail.message', lambda value: value.id)
    def message_post(self, **kwargs):
        message = super(MailThread, self).message_post(**kwargs)

        leave_env = self.env['hr.leave']
        for recipient in message.notification_ids.mapped('res_partner_id'):
            leave = leave_env.search([
                ('state', '=', 'validate'),
                ('date_from', '<=', fields.Date.today()),
                ('date_to', '>=', fields.Date.today()),
                ('employee_id.user_id.partner_id', '=', recipient.id),
            ], limit=1)
            
            if leave and leave.alternate_follower_id:
                message.write({
                    'notification_ids': [(0, 0, {
                        'res_partner_id': leave.alternate_follower_id.partner_id.id,
                        # 'notification_type': 'email',
                    })]
                })
        return message
