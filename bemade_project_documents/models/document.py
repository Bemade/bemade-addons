from odoo import models, fields, api


class Document(models.Model):
    _inherit = 'documents.document'

    external_approver_ids = fields.Many2many('res.partner')

