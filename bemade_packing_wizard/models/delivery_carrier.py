# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError

class DeliveryCarrier(models.Model):
    _inherit = 'delivery.carrier'

    # this allow us to enable the auto create package feature per delivery.carrier
    # default is False to avoid impacting Odoo's default behavior on Test
    auto_create_package = fields.Boolean('Auto Create Package', default=False)