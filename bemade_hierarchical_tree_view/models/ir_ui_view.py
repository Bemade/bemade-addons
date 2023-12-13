from odoo import models, fields


class View(models.Model):
    _inherit = "ir.ui.view"

    type = fields.Selection(
        selection_add=[('htree', 'Hierarchical Tree')]
    )


class ActionView(models.Model):
    _inherit = "ir.actions.act_window.view"

    view_mode = fields.Selection(
        selection_add=[('htree', 'Hierarchical Tree')],
        ondelete={'htree': 'cascade'},
    )
