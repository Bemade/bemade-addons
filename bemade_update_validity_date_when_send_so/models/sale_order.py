# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from datetime import datetime, timedelta
from itertools import groupby
import json

from odoo import api, fields, models, SUPERUSER_ID, _
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.osv import expression
from odoo.tools import float_is_zero, html_keep_url, is_html_empty

from odoo.addons.payment import utils as payment_utils


class SaleOrder(models.Model):
    _inherit = "sale.order"

    def action_quotation_send(self):
        self.ensure_one()
        self.date_order = datetime.now()
        self.validity_date = datetime.now() + timedelta(days=30)
        super(SaleOrder, self).action_quotation_send()

