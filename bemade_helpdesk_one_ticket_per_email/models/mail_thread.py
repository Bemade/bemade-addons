from odoo import models, fields, api, _


class MailThread(models.AbstractModel):
    _inherit = 'mail.thread'

    @api.model
    def message_route(self, message, message_dict, model=None, thread_id=None, custom_values=None):
        res = super().message_route(message, message_dict, model, thread_id, custom_values)
        main_route = None
        for tuple in res:
            if tuple[0] in ('helpdesk.team', 'helpdesk.ticket'):
                if not main_route:
                    main_route = tuple
                else:
                    res.remove(tuple)
        return res
