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
    _inherit = "sale.order"  # SaleOrder model inherits the 'sale.order' object in Odoo

    def action_quotation_send(self):
        """This function is executed when the 'Send Quotation' button is clicked."""
        # Ensures that the current recordset is exactly one record
        self.ensure_one()
        # Updates the order date to the current date and time
        self.date_order = datetime.now()
        # Updates the validity date to 30 days from now
        self.validity_date = datetime.now() + timedelta(days=30)
        # Calls the original 'action_quotation_send' method from 'sale.order'
        super(SaleOrder, self).action_quotation_send()
