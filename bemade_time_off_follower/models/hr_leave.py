from odoo import models, fields, api


class HrLeave(models.Model):
    _inherit = 'hr.leave'

    alternate_follower_id = fields.Many2one(
        comodel_name='res.users',
        string='Alternate Follower',
        help='User who will receive a copy of all communications related to this leave',
    )
