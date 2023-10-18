from odoo import models, fields, _, api


class DocumentRevision(models.Model):
    _name = "documents.revision"
    _description = "Document Revision"
    _sql_constraints = [
        ('name_document_id_unique', 'unique (name,document_id)',
         'The revision name must be unique for each document.')]

    name = fields.Char()
    document_id = fields.Many2one('documents.document', required=True)
    attachment_id = fields.Many2one('ir.attachment', required=True)

    @api.model_create_multi
    def create(self, vals_list):
        """
        Creates one or more new document revisions. Each revision created replaces the
        ir.attachment tied to the document with the one provided in this revision. It
        also supersedes the previous revision, updating the document's
        current_revision_id and carrying a link to the previous revision in
        previous_revision_id.

        :param vals_list: Dictionary or list of dictionaries
        :return:
        """
        res = super().create(vals_list)
        for rec in res:
            # When we create a new revision, we need to replace the attachment linked
            # to the document to keep it on the latest version.
            rec.document_id.attachment_id = rec.attachment_id
            # Then we update the current revision to this new revision and link
            # back to the previous revisions
            rec.previous_revision_id = rec.document_id.current_revision_id
            rec.document_id.current_revision_id = rec
        return res
