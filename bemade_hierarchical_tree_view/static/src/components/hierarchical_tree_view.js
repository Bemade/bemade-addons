/** @odoo-module **/

import { listView } from "@web/views/list/list_view";
import { HierarchicalTreeViewController } from "./hierarchical_tree_view_controller";
import { HierarchicalTreeViewRenderer } from "./hierarchical_tree_view_renderer";
import { registry } from "@web/core/registry";
import {HierarchicalTreeArchParser} from "./hierarchical_tree_arch_parser";

const HierarchicalTreeView = {
    ...listView,
    type: "htree",
    display_name: "Hierarchical Tree",
    icon: "fa fa-sitemap",
    accessKey: "h",
    Controller: HierarchicalTreeViewController,
    Renderer: HierarchicalTreeViewRenderer,
    ArchParser: HierarchicalTreeArchParser,
}

registry.category("views").add("htree", HierarchicalTreeView);
