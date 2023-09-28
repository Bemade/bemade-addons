from odoo import models, fields, _
from odoo.exceptions import UserError


class DocumentRevisionWizard(models.TransientModel):
    _name = 'documents.revision.wizard'
    _description = 'Allows the creation of new document revisions'

    document_id = fields.Many2one('documents.document', 'Document')
    file = fields.Binary('File to upload')
    revision_name = fields.Char()

    def default_get(self, fields_list):
        ctx = self._context
        if 'active_ids' in ctx and len(ctx.get('active_ids')) > 1:
            raise UserError(_('You can only create revisions for one document at a time.'))
        if 'active_id' not in ctx:
            raise UserError(_('You must select a document for which you are creating a revision.'))
        self.document_id = self.env['documents.document'].browse(ctx.get('active_id'))
