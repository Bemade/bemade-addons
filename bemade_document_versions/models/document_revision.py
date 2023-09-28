from odoo import models, fields, _, api


class DocumentRevision(models.Model):
    _name = "documents.revision"
    _description = "Document Revision"

    document_id = fields.Many2one('documents.document', required=True)
    attachment_id = fields.Many2one('ir.attachment', required=True)
    previous_revision_id = fields.Many2one('documents.revision', 'Previous Revision')
    next_revision_id = fields.One2many('documents.revision', 'previous_revision_id')

    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        for rec in res:
            # When we create a new revision, we need to replace the attachment linked
            # to the document to keep it on the latest version.
            rec.document_id.attachment_id = rec.attachment_id
            # Then we update the current revision to this new revision and link
            # back to the previous revisions
            rec.previous_revision_id = rec.document_id.current_revision_id
            rec.document_id.current_revision_id = rec
