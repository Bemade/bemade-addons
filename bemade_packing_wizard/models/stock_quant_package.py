# -*- coding: utf-8 -*-

from odoo import models, fields, api
from odoo.exceptions import ValidationError


class StockQuantPackage(models.Model):

    _inherit = 'stock.quant.package'

    length = fields.Float('Length')
    width = fields.Float('Width')
    height = fields.Float('Height')

    carrier_id = fields.Many2one( comodel_name='delivery.carrier',
                                  string='Carrier',
                                  help="Carrier use to create package.",
                                  compute='_compute_package_carrier' )

    provider = fields.Selection( selection=lambda self: self._get_provider(),
                                 string='Provider',
                                 help="Provider to create package.",
                                 compute='_compute_package_carrier' )

    auto_create_package = fields.Boolean( string='Auto Create Package',
                                          compute='_compute_auto_create_package' )


    @api.depends('carrier_id')
    def _compute_auto_create_package(self):
        # Look so much like a related field
        for record in self:
            record.auto_create_package = record.carrier_id.auto_create_package if record.carrier_id else False


    def _compute_package_carrier(self):
        move_line = self.env['stock.move.line'].search([('result_package_id', '=', self.id)])
        # This also look like a related field and might not even be needed as we only need it to get the provider
        self.carrier_id = move_line.carrier_id
        delivery_types_available =  [item[0] for item in self.env['stock.package.type']._fields['package_carrier_type'].selection]
        # This is a bit of a hack to get the provider from the carrier_id, depending if carrier is integrated or not
        if self.carrier_id.delivery_type not in delivery_types_available:
            self.provider = False
        else:
            self.provider = move_line.carrier_id.delivery_type



    def _get_provider(self):
        # just cloning the selection from stock.package.type tru a lambda function
        return self.env['stock.package.type']._fields['package_carrier_type'].selection


    def write(self, vals):
        if 'length' in vals and 'width' in vals and 'height' in vals:
            # check if length, width, height are greater than 0
            if vals['length'] <= 0 or vals['width'] <= 0 or vals['height'] <= 0:
                raise ValidationError('Length, width, and height must be greater than 0.')
            # Make sure length is always greater than width, otherwise swap them
            if vals['length'] < vals['width']:
                vals['length'], vals['width'] = vals['width'], vals['length']
            # check if existing package_type exists
            package_type = self.env['stock.package.type'].search([
                ('width', '=', vals['width']),
                ('height', '=', vals['height']),
                ('packaging_length', '=', vals['length']),
                ('package_carrier_type', '=', self.provider)
            ], limit=1)

            # if not, create new package_type
            if not package_type:
                package_type = self.env['stock.package.type'].create({
                    'name': f'Box {vals["length"]}x{vals["width"]}x{vals["height"]}',
                    'width': vals['width'],
                    'height':  vals['height'],
                    'packaging_length': vals['length'],
                    'package_carrier_type': self.provider
                })

            # update package_type_id
            vals['package_type_id'] = package_type.id

        res = super(StockQuantPackage, self).write(vals)
        return res