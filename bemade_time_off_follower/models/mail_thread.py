from odoo import models, api, fields
import logging

_logger = logging.getLogger(__name__)

class MailThread(models.AbstractModel):
    _inherit = 'mail.thread'

    @api.returns('mail.message', lambda value: value.id)
    def message_post(self, **kwargs):
        message = super(MailThread, self).message_post(**kwargs)

        for recipient in message.notification_ids.mapped('res_partner_id'):
            user = self.env['res.users'].search([('partner_id', '=', recipient.id)], limit=1)
            if user:
                employee = self.env['hr.employee'].search([('user_id', '=', user.id)], limit=1)

            if employee:
                employee_id = employee.id
                leaves = self.sudo().env['hr.leave'].search([
                    ('state', '=', 'validate'),
                    ('date_from', '<=', fields.Date.today()),
                    ('employee_id', '=', employee_id),
                    ('date_to', '>=', fields.Date.today()),
                ])
                for leave in leaves:
                    if leave.employee_id.user_id.partner_id.id == recipient.id and leave.alternate_follower_id:
                        _logger.info(f"adding {leave.alternate_follower_id.partner_id.name} as follower for {recipient.name} while on time off.")
                        message.write({
                            'notification_ids': [(0, 0, {
                                'res_partner_id': leave.alternate_follower_id.partner_id.id,
                            })]
                        })
        return message
