# Copyright 2025 Bemade Inc.
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

import logging

from odoo import api, models
from odoo.tools.mail import decode_message_header

_logger = logging.getLogger(__name__)


class MailThread(models.AbstractModel):
    _inherit = "mail.thread"

    @api.model
    def message_parse(self, message, save_original=False):
        msg_dict = super().message_parse(message, save_original=save_original)
        raw = decode_message_header(message, 'Auto-Submitted')
        # RFC 3834 allows parameters after semicolons, e.g.
        # "auto-replied; trigger=other" — take only the base value.
        base_value = raw.split(';')[0].strip().lower() if raw else ''
        msg_dict['auto_submitted'] = base_value
        return msg_dict

    @api.model
    def _message_route_process(self, message, message_dict, routes):
        # auto_submitted is added by message_parse for loop detection but is not
        # a valid message_post parameter in Odoo 18 — remove it before routing.
        message_dict.pop('auto_submitted', None)
        return super()._message_route_process(message, message_dict, routes)

    @api.model
    def _detect_loop_headers(self, msg_dict):
        if super()._detect_loop_headers(msg_dict):
            return True

        Settings = self.env['res.config.settings'].sudo()
        if not Settings._get_param_as_bool(
            'mail_loop_prevention.enabled', default=True
        ):
            return False

        auto_submitted = msg_dict.get('auto_submitted', '')
        if not auto_submitted or auto_submitted == 'no':
            return False

        if auto_submitted == 'auto-replied':
            _logger.info(
                'Mail loop prevention: dropping auto-replied email from %s '
                '(Message-Id %s)',
                msg_dict.get('email_from'),
                msg_dict.get('message_id'),
            )
            return True

        if auto_submitted == 'auto-generated':
            if Settings._get_param_as_bool(
                'mail_loop_prevention.block_auto_generated', default=False
            ):
                _logger.info(
                    'Mail loop prevention: dropping auto-generated email '
                    'from %s (Message-Id %s)',
                    msg_dict.get('email_from'),
                    msg_dict.get('message_id'),
                )
                return True

        return False
