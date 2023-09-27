# -*- coding: utf-8 -*-
from odoo import models, fields, api
from math import ceil
from odoo.exceptions import ValidationError


class ChooseDeliveryPackage(models.TransientModel):
    _inherit = 'choose.delivery.package'

    length = fields.Float('Length')
    width = fields.Float('Width')
    height = fields.Float('Height')

    auto_create_package = fields.Boolean(
        string='Auto Create Package',
    )

    provider = fields.Selection(
        selection=lambda self: self._get_provider(),
        string='Provider',
        help="Provider to create package.",
    )

    @api.model
    def default_get(self, fields_list):
        defaults = super().default_get(fields_list)
        if 'provider' in fields_list:
            picking = self.env['stock.picking'].browse(defaults.get('picking_id'))

            delivery_types_available = [item[0] for item in self.env['stock.package.type']._fields['package_carrier_type'].selection]
            if picking.carrier_id.delivery_type not in delivery_types_available:
                defaults['provider'] = False
                defaults['auto_create_package'] = False
            else:
                defaults['provider'] = picking.carrier_id.delivery_type
                defaults['auto_create_package'] = picking.carrier_id.auto_create_package
        return defaults


    def _get_provider(self):
        return self.env['stock.package.type']._fields['package_carrier_type'].selection

    # def _compute_auto_create_package(self):
    #     for record in self:
    #         record.auto_create_package = record.carrier_id.auto_create_package if record.carrier_id else False
    #
    # def _compute_provider(self):
    #     move_line = self.env['stock.move.line'].search([('result_package_id', '=', self.id)])
    #     delivery_types_available =  [item[0] for item in self.env['stock.package.type']._fields['package_carrier_type'].selection]
    #     if self.picking_id.carrier_id.delivery_type not in delivery_types_available:
    #         self.provider = False
    #     else:
    #         self.provider = move_line.carrier_id.delivery_type
    #


    def action_put_in_pack(self):
        if self.auto_create_package:
            if self.width <= 0 or self.height <= 0 or self.length <= 0:
                raise ValidationError('Length, width, and height must be greater than 0.')

            if self.length < self.width:
                self.length, self.width = self.width, self.length

            delivery_package_type = self.env['stock.package.type'].search([
                ('width', '=', self.width),
                ('height', '=', self.height),
                ('packaging_length', '=', self.length),
                ('package_carrier_type', '=', self.provider)
            ], limit=1)

            if not delivery_package_type:
                delivery_package_type = delivery_package_type.create({
                    'name': f'Box {vals["width"]}x{vals["height"]}x{vals["length"]}',
                    'width': self.width,
                    'height': self.height,
                    'packaging_length': self.length,
                    'package_carrier_type': self.provider
                })

            self.delivery_package_type_id = delivery_package_type.id
        result = super().action_put_in_pack()
        return result