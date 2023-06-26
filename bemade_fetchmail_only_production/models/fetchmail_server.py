# Copyright (C) 2023 Bemade.org
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging

# Import the required classes and decorators from Odoo
from odoo import api, models
from urllib.parse import urlparse

_logger = logging.getLogger(__name__)

class fetchmail_server(models.Model):
    _inherit = 'fetchmail.server'

    @api.model
    def fetch_mail(self):
        if urlparse(self.env['ir.config_parameter'].sudo().get_param('web.base.url')).netloc == \
                urlparse('https://erp.durpro.com/').netloc:
            return super(fetchmail_server, self).fetch_mail()
        else:
            # Add log message
            _logger.info("Trying to fetch email, current URL don't match with production URL, so we don't fetch email")
            return True
