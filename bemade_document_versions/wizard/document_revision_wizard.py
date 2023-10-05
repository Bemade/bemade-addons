from odoo import models, fields, _, api
from odoo.exceptions import UserError


class DocumentRevisionWizard(models.TransientModel):
    _name = 'documents.revision.wizard'
    _description = 'Allows the creation of new document revisions'

    document_id = fields.Many2one('documents.document', 'Document')
    document_name = fields.Char()
    file = fields.Binary('File to upload')
    revision_name = fields.Char(required=True)
    revision_sequence_prefix = fields.Char(string='Sequence Prefix')
    revision_sequence_suffix = fields.Char(string='Sequence Suffix')
    revision_sequence_padding = fields.Integer(string='Sequence Padding',
                                               help="Number of digits to show in the"
                                                    " sequence number. A value of 2 will"
                                                    " generate sequence numbers like 01,"
                                                    " 02, 03, etc.")

    def default_get(self, fields_list):
        ctx = self._context
        vals = {}
        if 'document_id' not in ctx:
            raise UserError(
                _('You must select a document for which you are creating a revision.'))
        document = self.env['documents.document'].browse(ctx.get('document_id'))
        vals['document_name'] = document.name
        vals['document_id'] = document.id
        sequence = document.revision_sequence or self.env.ref(
            'bemade_document_versions.document_revision_sequence_default')
        if document.revision_sequence:
            vals['revision_name'] = self.document_id.get_next_revision_name()
        else:
            vals['revision_name'] = sequence.get_next_char(0)
        vals['revision_sequence_prefix'] = sequence.prefix
        vals['revision_sequence_suffix'] = sequence.suffix
        vals['revision_sequence_padding'] = sequence.padding
        return vals

    def action_upload_revision(self):
        for wizard in self:
            if not wizard.file:
                raise UserError(_('You must upload a file.'))
            if not wizard.revision_name:
                raise UserError(_('Revision name cannot be empty.'))
            prev_attachment = wizard.document_id.attachment_id
            attachment = self.env['ir.attachment'].with_context(
                {'no_document': True}).create({
                'name': prev_attachment.name,
                'datas': wizard.file,
                'res_model': prev_attachment.res_model,
                'res_id': prev_attachment.res_id,
                'company_id': prev_attachment.company_id.id,
                'public': prev_attachment.public,
            })
            if not wizard.document_id.revision_sequence:
                wizard.document_id.set_up_revisions(wizard.revision_name,
                                                    wizard.revision_sequence_prefix,
                                                    wizard.revision_sequence_suffix,
                                                    wizard.revision_sequence_padding)
            else:
                self.env['documents.revision'].create({
                    'document_id': wizard.document_id.id,
                    'attachment_id': attachment.id,
                    'name': wizard.revision_name,
                    'attachment_id': attachment.id,
                })
