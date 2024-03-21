from odoo import models, fields, api, _, Command


class Partner(models.Model):
    _inherit = 'res.partner'

    root_ancestor = fields.Many2one(
        comodel_name='res.partner',
        string='Root Ancestor',
        compute='_compute_root_ancestor',
        store=True,
        recursive=True
    )

    @api.depends('parent_id', 'parent_id.root_ancestor')
    def _compute_root_ancestor(self):
        for rec in self:
            rec.root_ancestor = rec.parent_id and rec.parent_id.root_ancestor or rec
