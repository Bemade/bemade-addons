/** @odoo-module **/

import ListController from 'web.ListController';
import ListView from 'web.ListView';
const viewRegistry = require('web.view_registry');

const AliasesListController = ListController.extend({
    // buttons_template must match the t-name on the template for the button (static xml)
    buttons_template: 'mail.mailcow_aliases_list_view_buttons',
    events: _.extend({}, ListController.prototype.events, {
        'click .o_button_sync_aliases': '_onSyncAliases',
    }),
    // This may need to be async function() if there needs to be an await this._rpc({ ... }); call to not reload early
    _onSyncAliases: function () {
        this._rpc({
            model: 'mail.mailcow.alias',
            method: 'sync_aliases',
            args: [],
        });
        // Couldn't test this for real, but it runs the action. May need a this.reload()
    },
});

const AliasesListView = ListView.extend({
    config: _.extend({}, ListView.prototype.config, {
        Controller: AliasesListController,
    }),
});

// key must match with the js_class attribute of the tree view you want to modify
viewRegistry.add('mail_mailcow_aliases_tree', AliasesListView);
