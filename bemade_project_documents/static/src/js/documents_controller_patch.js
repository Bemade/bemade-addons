/** @odoo-module **/

const DocumentsListController = require('documents.DocumentsListController');
const DocumentsKanbanController = require('documents.DocumentsKanbanController');
const DocumentsControllerMixin = require('documents.controllerMixin');

import {patch} from 'web.utils';

const prototype_addins = {
    _onClickRequestApprovals: function (ev) {
        ev.preventDefault();
        const context = this.model.get(this.handle, {raw: true}).getContext();
        this.do_action('bemade_project_documents.action_request_approval_form', {
            additional_context: {
                default_document_ids: this._selectedRecordIds,
            },
            on_close: () => this.reload(),
        });
    },
    _makeFileUpload({ recordId }) {
        const context = this.model.get(this.handle, {raw: true}).getContext();
        return Object.assign({
            res_model: context.default_res_model || false,
            res_id: context.default_res_id || false,
        }, this._super(...arguments));
    },
    _makeFileUploadFormDataKeys({ recordId }) {
        const context = this.model.get(this.handle, {raw: true}).getContext();
        return Object.assign({
            res_model: context && context.default_res_model,
            res_id: context && context.default_res_id,
        }, this._super(...arguments));
    },
};

const patch_name = "bemade_project_documents.DocumentsControllerPatch";

patch(DocumentsControllerMixin, patch_name, {
    events: _.extend({}, DocumentsControllerMixin.events, {
        'click .o_documents_kanban_request_approvals': '_onClickRequestApprovals',
    }),
});
patch(DocumentsListController.prototype, patch_name, prototype_addins);
patch(DocumentsKanbanController.prototype, patch_name, prototype_addins);
