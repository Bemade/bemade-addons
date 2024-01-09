/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { FormController } from "@web/views/form/form_controller";
import { useService } from "@web/core/utils/hooks";

patch(FormController.prototype, "bemade_full_formview_from_modal.FormController", {
    setup () {
        this._super();
        this.action = useService("action")
    },
    onOpenButtonClicked: function () {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: this.props.resModel,
            res_id: this.props.resId,
            views: [[false, "form"]],
            target: "current",
            context: this.props.context,
        })
    }
});
