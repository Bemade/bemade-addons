from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.http import request, route
from odoo.exceptions import AccessError, MissingError
from odoo import _


class DocumentCustomerPortal(CustomerPortal):

    def _prepare_home_portal_values(self, counters):
        rtn = super()._prepare_home_portal_values(counters)
        domain = self._prepare_documents_domain()
        rtn['documents_count'] = request.env['documents.document'].search_count(domain)
        return rtn

    @route('/my/documents', type='http', auth='user', website=True)
    def portal_my_documents(self, **kwargs):
        values = self._prepare_portal_layout_values()
        Documents = request.env['documents.document']
        domain = self._prepare_documents_domain()
        documents_count = Documents.search_count(domain)
        documents = Documents.search(domain)
        values.update({
            'documents_count': documents_count,
            'documents': documents.sudo(),
            'default_url': '/my/documents',
            'page_name': 'my_documents',
        })
        return request.render("bemade_documents_portal.portal_my_documents", values)

    def _prepare_documents_domain(self):
        partner = request.env.user.partner_id
        user = request.env.user
        """Helper method intended to be overridden for future modules."""
        return ['|',
                ('partner_id', '=', partner.id),
                ('owner_id', '=', user.id),
                ]

    def _render_record_template(self, values):
        """ Override this method to apply a different template for a single document
        record on the portal. """
        return request.render("bemade_documents_portal.document_portal_template", values)

    @route('/my/documents/<int:document_id>', type='http', auth='user', website=True)
    def portal_document_page(self, document_id, download=False, **kwargs):
        document = request.env['documents.document'].browse(document_id)
        if not document:
            raise MissingError(_('This document does not exist.'))
        if download:
            return self._download_attachment(document)
        values={
            'document': document,
            'page_name': 'my_documents',
            'action': document._get_portal_return_action(),
        }
        return self._render_record_template(values)

    def _download_attachment(self, document):
        attachment = document.attachment_id
        headers = [
            ('content-type', attachment.mimetype),
            ('content-length', attachment.file_size),
            ('content-disposition', f'attachment; filename="{document.name}"')
        ]
        return request.make_response(attachment.raw, headers)
