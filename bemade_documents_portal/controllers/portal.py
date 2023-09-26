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
        """Helper method intended to be overridden for future modules."""
        partner = request.env.user.partner_id
        user = request.env.user
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
        values = {
            'document': document,
            'page_name': 'my_documents',
            'action': document._get_portal_return_action(),
        }
        return self._render_record_template(values)

    def _download_attachment(self, document):
        partner = request.env.user.partner_id
        if partner and self._check_portal_access(document, partner):
            attachment = document.attachment_id.sudo()
        headers = [
            ('content-type', attachment.mimetype),
            ('content-length', attachment.file_size),
            ('content-disposition', f'attachment; filename="{document.name}"')
        ]
        return request.make_response(attachment.raw, headers)

    def _check_portal_access(self, document, partner) -> bool:
        """
        Helper method to determine if a given partner has access to a document.

        This method is intended to be overridden should further access rights be granted.

        Note that this method does NOT replace the user-level ACL verification and is
        instead used to bypass these ACL checks when portal users are trying to download
        a document.

        In overriding, one should generally use the following form::

            new_condition = ...
            return super()._check_portal_access or new_condition

        :param document: The document in question.
        :param partner: The res_partner to check for portal access.
        :return: True if the partner should have access to the document, False otherwise.
        """
        return partner == document.partner_id
