/** @odoo-module **/

import { ListController } from "@web/views/list/list_controller";

export class HierarchicalTreeViewController extends ListController {

}

HierarchicalTreeViewController.props = {
    ...ListController.props,
    parentField: String,
    childField: String,
}
HierarchicalTreeViewController.defaultProps = {
    ...ListController.defaultProps,
    parentField: 'parent_id',
    childField: 'child_id',
}