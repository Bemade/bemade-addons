from odoo import models, fields, api


class Project(models.Model):
    _inherit = 'project.project'

    document_ids = fields.One2many('documents.document',
                                   compute='_compute_document_ids')

    def _compute_document_ids(self):
        for project in self:
            project.document_ids = self.env['documents.document'].search([
                ('res_model', '=', 'project.project'),
                ('res_id', '=', project.id),
            ])
