from odoo import models, fields, api, _
from odoo.exceptions import UserError


class Partner(models.Model):
    _inherit = 'res.partner'

    owned_team_ids = fields.One2many(comodel_name='sports.team',
                                     inverse_name='parent_id')
    staff_ids = fields.One2many(comodel_name='sports.team.staff',
                                inverse_name='team_id')
    team_staff_rel_ids = fields.One2many(comodel_name='sports.team.staff',
                                         inverse_name='partner_id',
                                         string='Teams Served',
                                         help='The teams this person works for.')

