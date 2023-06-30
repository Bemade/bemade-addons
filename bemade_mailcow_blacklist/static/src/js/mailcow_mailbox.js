/** @odoo-module **/

import ListController from 'web.ListController';
import ListView from 'web.ListView';
const viewRegistry = require('web.view_registry');

const MailboxesListController = ListController.extend({
    // buttons_template must match the t-name on the template for the button (static xml)
    buttons_template: 'mail.mailcow_mailbox_list_view_buttons',
    events: _.extend({}, ListController.prototype.events, {
        'click .o_button_sync_mailboxes': '_onSyncMailboxes',
    }),
    // This may need to be async function() if there needs to be an await this._rpc({ ... }); call to not reload early
    _onSyncMailboxes: function () {
        this._rpc({
            model: 'mail.mailcow.mailbox',
            method: 'sync_mailboxes',
            args: [],
        });
        // Couldn't test this for real, but it runs the action. May need a this.reload()
    },
});

const MailboxesListView = ListView.extend({
    config: _.extend({}, ListView.prototype.config, {
        Controller: MailboxesListController,
    }),
});

// key must match with the js_class attribute of the tree view you want to modify
viewRegistry.add('mail_mailcow_mailbox_tree', MailboxesListView);
