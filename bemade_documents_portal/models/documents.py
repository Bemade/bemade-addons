from odoo import models, fields


class Document(models.Model):
    _name = 'documents.document'
    _inherit = ['documents.document', 'portal.mixin']

    def _compute_access_url(self):
        super()._compute_access_url()
        for document in self:
            document.access_url = f'/my/documents/{document.id}'

    def _get_portal_return_action(self):
        """ Return the action used to display documents when returning from customer
        portal."""
        self.ensure_one()
        return self.env.ref('documents.document_action')