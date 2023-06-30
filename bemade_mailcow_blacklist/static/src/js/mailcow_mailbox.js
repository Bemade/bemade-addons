/** @odoo-module **/

import ListController from 'web.ListController';
import ListView from 'web.ListView';
const viewRegistry = require('web.view_registry');

const MailboxesListController = ListController.extend({
    buttons_template: 'mail.mailcow_mailbox_list_view_buttons',
    events: _.extend({}, ListController.prototype.events, {
        'click .o_button_sync_mailboxes': '_onSyncMailboxes',
    }),
    _onSyncMailboxes: function () {
        this._rpc({
            model: 'mail.mailcow.mailbox',
            method: 'sync_mailboxes',
            args: [],
        });
    },
});

const MailboxesListView = ListView.extend({
    config: _.extend({}, ListView.prototype.config, {
        Controller: MailboxesListController,
    }),
});

viewRegistry.add('mail_mailcow_mailbox_tree', MailboxesListView);
