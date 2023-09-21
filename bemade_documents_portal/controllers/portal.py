from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.http import request, route


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
        print(f"Documents: {documents_count}...")
        for doc in documents:
            print(doc.name)
        values.update({
            'documents_count': documents_count,
            'documents': documents.sudo(),
            'default_url': '/my/documents',
            'page_name': 'my_documents',
        })
        print
        return request.render("bemade_documents_portal.portal_my_documents", values)

    def _prepare_documents_domain(self):
        partner = request.env.user.partner_id
        user = request.env.user
        """Helper method intended to be overridden for future modules."""
        return ['|',
                ('partner_id', '=', partner.id),
                ('owner_id', '=', user.id),
                ]
