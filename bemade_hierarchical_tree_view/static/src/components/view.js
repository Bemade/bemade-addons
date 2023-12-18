/** @odoo-module **/

import { View } from "@web/views/view";
import { patch } from "@web/core/utils/patch";
import { HierarchicalTreeViewController } from "./hierarchical_tree_view_controller";
import { onWillRender } from "@odoo/owl";

patch(View.prototype, "bemade_hierarchical_tree_view.View", {
    setup() {
        this._super();
        /*
        If we're rendering a hierarchical tree view, we need to remove the parent and
        child fields from the groupBy parameters we pass down through the component
        tree. This is necessary since this view type will treat the parent and child
        groupings differently. We do it here instead of doing it in the controller
        because the Controller would have to either modify its props or seriously
        redefine the data used within the template, which we are trying to avoid for
        code duplication reasons.
         */
        if ( this.Controller.prototype === HierarchicalTreeViewController.prototype ) {
            onWillRender(() => {
                let parentField = this.Controller.parentField
                let childField =  this.Controller.childField
                let parentIndex = this.groupBy.indexOf(parentField);
                let childIndex = this.groupBy.indexOf(childField);
                if (parentIndex) {
                    this.groupBy.splice(parentIndex, 1);
                }
                if (childField) {
                    this.groupBy.splice(childIndex, 1);
                }
            });
        }
    },
});
