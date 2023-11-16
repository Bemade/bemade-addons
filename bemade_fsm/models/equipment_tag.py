from odoo import api, fields, models


class EquipmentTag(models.Model):
    _name = "bemade_fsm.equipment.tag"
    _description = 'Field service equipment category'

    name = fields.Char('Name', required=True, translate=True)
    color = fields.Integer('Color Index', default=10)

    _sql_constraints = [
        ('name_uniq', 'unique (name)', "Tag name already exists !"),
    ]
