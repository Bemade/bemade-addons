from odoo import api, fields, models


class EquipmentType(models.Model):
    _name = 'bemade_fsm.equipment.type'
    _description = 'Field service equipment type'
    _order = 'id'

    name = fields.Char(string='Intervention Name', required=True, translate=True)
