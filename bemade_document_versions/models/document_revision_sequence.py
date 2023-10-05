from odoo import models, fields, api, _
from odoo.exceptions import UserError


class DocumentRevisionSequence(models.Model):
    _inherit = 'ir.sequence'
    # Would prefer to inherit and make a new model, but the way ir.sequence is
    # implemented has a lot of hard coded references to "ir.sequence" for all the
    # database operations.

    document_id = fields.Many2one('documents.document', 'Document',
                                  ondelete='cascade')
