from odoo.addons.documents.controllers.main import ShareRoute
from odoo.http import route, request
import json


class DocumentsController(ShareRoute):

    @route('/documents/upload_attachment', type='http', methods=['POST'], auth='user')
    def upload_document(self, folder_id, ufile, tag_ids, res_model, res_id,
                        document_id=False, partner_id=False, owner_id=False):
        res = super().upload_document(folder_id, ufile, tag_ids, document_id, partner_id,
                                      owner_id)
        res_data = json.loads(res.data)
        if 'ids' in res_data and res_model and res_id:
            docs = request.env['documents.document'].browse(res_data['ids'])
            docs.write({'res_model': res_model, 'res_id': res_id})
        return res
