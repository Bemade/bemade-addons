from odoo import models, fields, api


class RequestDocumentApprovalsWizard(models.TransientModel):
    _name = 'project_documents.approval.wizard'

    project_id = fields.Many2one('project.project')

