# -*- coding: utf-8 -*-
from odoo import models, fields, api
from math import ceil
from odoo.exceptions import ValidationError
class ChooseDeliveryPackage(models.TransientModel):
    _inherit = 'choose.delivery.package'

    length = fields.Float('Length')
    width = fields.Float('Width')
    height = fields.Float('Height')
    auto_create_package = fields.Boolean(string='Auto Create Package', default=False)
    provider = fields.Selection(selection=lambda self: self._get_provider(), string='Provider')

    @api.model
    def default_get(self, fields_list):
        # This is a bit of a hack to get the provider from the carrier_id, depending if carrier is integrated or not
        defaults = super().default_get(fields_list)
        if 'provider' in fields_list:
            # get related picking
            picking = self.env['stock.picking'].browse(defaults.get('picking_id'))
            # generate list of available delivery types keeping only the first element of the tuple
            delivery_types_available = \
                [item[0] for item in self.env['stock.package.type']._fields['package_carrier_type'].selection]
            # if carrier is not integrated, provider is False
            if picking.carrier_id.delivery_type not in delivery_types_available:
                defaults['provider'] = False
                defaults['auto_create_package'] = False
            else:
                # if carrier is integrated, provider is the delivery_type and carry auto_create_package from carrier
                defaults['provider'] = picking.carrier_id.delivery_type
                defaults['auto_create_package'] = picking.carrier_id.auto_create_package
        return defaults


    def _get_provider(self):
        # just cloning the selection from stock.package.type tru a lambda function
        return self.env['stock.package.type']._fields['package_carrier_type'].selection


    def action_put_in_pack(self):
        # this override is call only for delivery.carrier with auto_create_package = True.  Ideal for odoo test
        if self.auto_create_package:
            if self.width <= 0 or self.height <= 0 or self.length <= 0:
                # Obviously, we need value for our wizard to work
                raise ValidationError('Length, width, and height must be greater than 0.')

            # Make sure length is always greater than width, otherwise swap them
            if self.length < self.width:
                self.length, self.width = self.width, self.length

            # that search is carier.delivery integration agnostic
            delivery_package_type = self.env['stock.package.type'].search([
                ('width', '=', self.width),
                ('height', '=', self.height),
                ('packaging_length', '=', self.length),
                ('package_carrier_type', '=', self.provider)
            ], limit=1)

            # if no package type found, create one
            if not delivery_package_type:
                delivery_package_type = delivery_package_type.create({
                    'name': f'Box {self.width}x{self.height}x{self.length}',
                    'width': self.width,
                    'height': self.height,
                    'packaging_length': self.length,
                    'package_carrier_type': self.provider
                })

            self.delivery_package_type_id = delivery_package_type.id
        result = super().action_put_in_pack()
        return result