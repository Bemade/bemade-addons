odoo.define('bemade_mailcow_blacklist.mailcow_mailbox', function (require) {
"use strict";

    var core = require('web.core');
    var ListController = require('web.ListController');
    var ListView = require('web.ListView');
    var viewRegistry = require('web.view_registry');

    var MailboxesListController = ListController.extend({
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

    var MailboxesListView = ListView.extend({
        config: _.extend({}, ListView.prototype.config, {
            Controller: MailboxesListController,
        }),
    });

    viewRegistry.add('mail.mailcow.mailbox', MailboxesListView);
});
