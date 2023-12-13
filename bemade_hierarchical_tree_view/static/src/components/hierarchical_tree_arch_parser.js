/** @odoo-module **/

import { ListArchParser }  from "@web/views/list/list_arch_parser";

export class HierarchicalTreeArchParser extends ListArchParser {
    parse(arch, models, modelName) {
        let modifiedArch = arch.replaceAll("htree", "tree");
        return super.parse(modifiedArch, models, modelName);
    }
};