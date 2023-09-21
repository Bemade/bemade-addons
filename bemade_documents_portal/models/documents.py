from odoo import models, fields


class Document(models.Model):
    _name = 'documents.document'
    _inherit = ['documents.document', 'portal.mixin']

    def _compute_access_url(self):
        super()._compute_access_url()
        for document in self:
            document.access_url = f'/my/documents/{document.id}'

