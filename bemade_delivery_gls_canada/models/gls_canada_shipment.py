from odoo import models, fields, api, _


class GLSCanadaShipment(models.Model):
    _name = "gls.canada.shipment"
    _description = "A shipment booked with GLS Canada"

    shipment_id = fields.Integer(help="The shipment ID on the GLS side")

    sender_address_line_1 = fields.Char()
    sender_address_line_2 = fields.Char()
    sender_street_number = fields.Char()
    sender_street_name = fields.Char()
    sender_street_direction = fields.Char()
    sender_city = fields.Char()
    sender_state = fields.Char()
    sender_country = fields.Char()
    sender_postal_code = fields.Char()

    consignee_address_line_1 = fields.Char()
    consignee_address_line_2 = fields.Char()
    consignee_street_number = fields.Char()
    consignee_street_name = fields.Char()
    consignee_street_direction = fields.Char()
    consignee_city = fields.Char()
    consignee_state = fields.Char()
    consignee_country = fields.Char()
    consignee_postal_code = fields.Char()

    parcel_ids = fields.One2many('gls.canada.parcel', string='Parcels')

class GLSCanadaParcel(models.Model):
    _name = 'gls.canada.parcel'
    _description = 'A parcel in a shipment booked with GLS Canada'

    shipment_id = fields.Many2one('gls.canada.shipment', string='Shipment')
    parcel_id = fields.Integer(help="The parcel ID on the GLS side")

    weight = fields.Float()
    length = fields.Float()
    width = fields.Float()
    depth = fields.Float()
    note = fields.Char()
    status = fields.Integer()
    


