from odoo import api, fields, models
import os


class AttachmentCleanupWizard(models.TransientModel):
    _name = 'attachment.cleanup.wizard'
    _description = 'Attachment Cleanup Wizard'

    attachment_ids = fields.Many2many(
        'ir.attachment',
        string='Missing Attachments',
        readonly=True,
        help='Attachments that are not found in the filestore'
    )

    @api.model
    def default_get(self, fields_list):
        res = super(AttachmentCleanupWizard, self).default_get(fields_list)

        attachments_1 = self.sudo().env['ir.attachment'].search([])

        self._cr.execute("SELECT id FROM ir_attachment WHERE company_id = %s", (self.env.company.id,))

        attachments = self._cr.fetchall()

        filestore_location = self.env['ir.attachment']._filestore()

        missing_attachments = []
        for attachment_id in attachments:
            # if attachment.id == 47984:
            #     print(attachment.store_fname)
            attachment = self.env['ir.attachment'].browse(attachment_id)

            if attachment.store_fname:
                file_path = os.path.join(filestore_location, attachment.store_fname)
                if not os.path.exists(file_path):
                    missing_attachments.append(attachment.id)

        if missing_attachments:
            res.update({'attachment_ids': [(6, 0, missing_attachments)]})
        return res

    def action_cleanup_attachments(self):
        self.ensure_one()
        self.attachment_ids.unlink()
