from odoo import models, fields, _
from odoo.exceptions import UserError


class WorkflowActionRuleRevision(models.Model):
    _inherit = ['documents.workflow.rule']

    create_model = fields.Selection(selection_add=[('documents.revision', "Revision")])

    def create_record(self, documents=None):
        rv = super().create_record(documents=documents)
        if self.create_model == 'documents.revision':
            if len(documents) != 1:
                raise UserError(_('Document revisions must be added for one and '
                                  'only one document at a time.'))
            ctx = {'document_id': documents[0].id}
            ctx.update(self._context)
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'documents.revision.wizard',
                'name': 'New Revision',
                'target': 'new',
                'context': ctx,
                'views': [(self.env.ref(
                    'bemade_document_versions.document_revision_wizard_view_form').id,
                           'form')],
                'view_mode': 'form',
            }
