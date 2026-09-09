/** @odoo-module **/

import {DocumentsControlPanel} from "@documents/views/search/documents_control_panel";
import {patch} from "@web/core/utils/patch";

/**
 * Documents-side "Link to Record" entry point (task #3678 defect 1).
 *
 * The enterprise Documents app does NOT render the standard ActionMenus
 * component, so a server action bound via `binding_model_id` /
 * `binding_view_types` never surfaces in the Documents UI. The Documents app
 * builds its own "Action" dropdown in the `documents.ControlPanel` template and
 * a hard-coded cog-menu whitelist. So the only way to expose a new contextual
 * action is to add it to that custom dropdown.
 *
 * This patch adds an `onLinkToRecord` handler that reuses the stock
 * `documents.document.action_link_to_record()` (the same method our server
 * action calls), which opens the generic `link_to_record_wizard` (model picker
 * limited to mail.thread models, then record picker).
 */
patch(DocumentsControlPanel.prototype, {
  /**
   * True when every selected record is a real binary document with an
   * attachment. A document can now be linked to many records (task #3678),
   * so -- unlike the stock guard -- already-linked documents
   * (res_model !== 'documents.document') remain eligible too.
   */
  get canLinkToRecord() {
    const records = this.targetRecords;
    return (
      this.documentService.userIsInternal &&
      this.currentFolderId !== "TRASH" &&
      records.length > 0 &&
      records.every((r) => r.data.type === "binary" && r.data.attachment_id)
    );
  },

  /**
   * Open the stock "Link to Record" wizard on the selected documents.
   */
  async onLinkToRecord() {
    const documentIds = this.targetRecords.map((record) => record.data.id);
    if (!documentIds.length) {
      return;
    }
    const action = await this.orm.call("documents.document", "action_link_to_record", [
      documentIds,
    ]);
    if (action) {
      await this.action.doAction(action, {
        onClose: () => this.notifyChange(),
      });
    }
  },
});
