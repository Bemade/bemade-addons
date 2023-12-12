/** @odoo-module **/

import {patch} from "@web/core/utils/patch";
import {WithSearch} from "@web/search/with_search/with_search";
import {onWillRender} from "@odoo/owl";
import {HierarchicalTreeViewController} from "./hierarchical_tree_view_controller";

patch(WithSearch.prototype, "bemade_hierarchical_tree_view/with_search", {
    setup() {
        onWillRender(() => {
            let children = Object.hasOwn(this.__owl__, 'children') ? this.__owl__.children : null;
            if (children && Object.keys(children).length !== 0) {
                for (let childProp in children) {
                    let child = children[childProp];
                    if (Object.hasOwn(child, 'component')) {
                        let childComponent = child.component;
                        if (childComponent.prototype == HierarchicalTreeViewController.prototype) {
                            let parentField, childField = (childComponent.parentField, childComponent.childField)
                            let parentIndex = this.groupBy.indexOf(parentField);
                            let childIndex = this.groupBy.indexOf(childField);
                            if (parentIndex) {
                                this.groupBy.splice(parentField, 1);
                            }
                            if (childField) {
                                this.groupBy.splice(childField, 1);
                            }
                        }
                    }
                }
            }
        });
        this._super();
    }
});