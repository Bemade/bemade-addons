from odoo import models, api, fields
import logging

_logger = logging.getLogger(__name__)


class MailThread(models.AbstractModel):
    _inherit = 'mail.thread'

    def _notify_compute_recipients(self, message, msg_vals):
        recipients = super(MailThread, self)._notify_compute_recipients(message, msg_vals)

        for recipient in recipients:
            user = self.env['res.users'].search([('partner_id', '=', recipient['id'])], limit=1)
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
                    if leave.employee_id.user_id.partner_id.id == recipient['id'] and leave.alternate_follower_id:
                        _logger.info(
                            f"adding {leave.alternate_follower_id.partner_id.name} as follower for {employee.name} while on time off.")
                        recipients.append({
                            'id': leave.alternate_follower_id.partner_id.id,
                            'active': True,
                            'share': False,
                            'groups': leave.alternate_follower_id.groups_id.ids,
                            'notif': 'inbox',
                            'type': 'user'
                        })

        return recipients
