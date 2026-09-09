/** @odoo-module **/

import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

const cogMenuRegistry = registry.category("cogMenu");

/**
 * "Link existing document" cog-menu item.
 *
 * Appears in the cog menu of every mail.thread form view and opens the
 * record-side documents.link.wizard with the current record in context, so the
 * user can link one or more existing Documents records to it.
 *
 * Modeled on enterprise `sign`'s SignRequestCogMenu: the current record's
 * model/id are read from the action service's current controller, and the
 * mail.thread gate uses the presence of the `message_ids` field in the search
 * view fields (no extra RPC).
 */
export class LinkDocumentCogMenu extends Component {
    static template = "bemade_documents_link.LinkDocumentCogMenu";
    static components = { DropdownItem };
    static props = {};

    setup() {
        this.action = useService("action");
    }

    linkDocument() {
        // resModel is static on the controller props; resId comes from the
        // mutable current state (it changes for newly created records).
        const resModel = this.action.currentController.props.resModel;
        const resId = this.action.currentController.currentState?.resId;
        if (!resModel || !resId) {
            return;
        }
        this.action.doAction(
            {
                name: _t("Link Existing Document"),
                type: "ir.actions.act_window",
                res_model: "documents.link.wizard",
                view_mode: "form",
                views: [[false, "form"]],
                target: "new",
            },
            {
                additionalContext: {
                    active_model: resModel,
                    active_id: resId,
                },
            }
        );
    }
}

export const LinkDocumentCogMenuItem = {
    Component: LinkDocumentCogMenu,
    groupNumber: 20,
    isDisplayed: ({ config, searchModel }) => {
        // A mail.thread model exposes a `message_ids` field in its (search) view.
        const isMailThread = Boolean(searchModel.searchViewFields?.["message_ids"]);
        return (
            isMailThread &&
            config.actionType === "ir.actions.act_window" &&
            config.viewType === "form" &&
            searchModel.resModel !== "documents.document"
        );
    },
};

cogMenuRegistry.add("link-document-menu", LinkDocumentCogMenuItem, { sequence: 20 });
