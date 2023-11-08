from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)


class MailThread(models.AbstractModel):
    _inherit = 'mail.thread'

    @api.model
    def _message_route_process(self, message, message_dict, routes):
        helpdesk_routes = [r for r in routes if r[0] in ('helpdesk.ticket', 'helpdesk.team')]
        if len(helpdesk_routes) > 1:
            _logger.info("Messages contained multiple helpdesk routes. Only the first one will be used.")
            helpdesk_routes.remove(0)
            routes.remove(helpdesk_routes)
        return super()._message_route_process(message, message_dict, routes)
