from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class RequestDocumentApprovalsWizard(models.TransientModel):
    _name = 'project_documents.approval.wizard'

    document_ids = fields.Many2many('documents.document', string='Documents')
    partner_ids = fields.Many2many('res.partner', string="Recipients",
                                   help="""Contacts who will receive a request to
                                    approve the document.""")
    request_template = fields.Many2one('mail.template')

    def default_get(self, fields_list):
        if 'request_template' not in fields_list:
            self.request_template = self.env.ref()

    def request_approvals(self):
        self._validate_partners_have_emails()

    def _validate_partners_have_emails(self):
        for wizard in self:
            if any([not p.email for p in wizard.partner_ids]):
                raise ValidationError(_('Each partner must have an email address.'))
