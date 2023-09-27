from odoo import models, fields, api


class RequestDocumentApprovalsWizard(models.TransientModel):
    _name = 'project_documents.approval.wizard'

    document_ids = fields.Many2many('documents.document', string='Documents')
    partner_ids = fields.Many2many('res.partner')

    def request_approvals(self):
        pass