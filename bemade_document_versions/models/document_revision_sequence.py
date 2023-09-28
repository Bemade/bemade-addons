from odoo import models, fields, api, _


class DocumentRevisionSequence(models.Model):
    """ Creates an independent sequence for each Document when the document is set to
    track
    """
    _name = 'documents.revision.sequence'
    _inherit = 'ir.sequence'

    document_id = fields.Many2one('documents.document', 'Document', ondelete='cascade')