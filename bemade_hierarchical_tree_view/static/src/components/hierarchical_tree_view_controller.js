/** @odoo-module **/

import { ListController } from "@web/views/list/list_controller";

export class HierarchicalTreeViewController extends ListController {
    setup() {
        super.setup();
    }
}

HierarchicalTreeViewController.props = {
    ...ListController.props,
    parentField: {type: String, optional: true},
    childField: {type: String, optional: true},
}
HierarchicalTreeViewController.defaultProps = {
    ...ListController.defaultProps,
    parentField: 'parent_id',
    childField: 'child_id',
}
HierarchicalTreeViewController.template = "web.HierarchicalTreeView";