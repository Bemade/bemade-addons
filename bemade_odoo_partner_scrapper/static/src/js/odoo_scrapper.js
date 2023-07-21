/** @odoo-module **/

import ListController from 'web.ListController';
import ListView from 'web.ListView';

import KanbanController from 'web.KanbanController';
import KanbanView from 'web.KanbanView';

const viewRegistry = require('web.view_registry');

const OdooScrapperListController = ListController.extend({
    // buttons_template must match the t-name on the template for the button (static xml)
    buttons_template: 'odoo_scrapper.list_view_buttons',
    events: _.extend({}, ListController.prototype.events, {
        'click .o_button_get_partner': '_onGetPartnerClick',
    }),
    // This may need to be async function() if there needs to be an await this._rpc({ ... }); call to not reload early
    _onGetPartnerClick: function () {
        this._rpc({
            model: 'res.partner',
            method: 'get_odoo_partner',
            args: [],
        }).then(() => {
            this.reload();
        });
        // Couldn't test this for real, but it runs the action. May need a this.reload()
    },
});

export const OdooScrapperListView = ListView.extend({
    config: _.extend({}, ListView.prototype.config, {
        Controller: OdooScrapperListController,
    }),
});

// key must match with the js_class attribute of the tree view you want to modify
viewRegistry.add('res_partner_odoo_scrapper_tree', OdooScrapperListView);

const OdooScrapperKanbanController = KanbanController.extend({
    // buttons_template must match the t-name on the template for the button (static xml)
    buttons_template: 'odoo_scrapper.kanban_view_buttons',
    events: _.extend({}, KanbanController.prototype.events, {
        'click .o_button_get_partner': '_onGetPartnerClick',
    }),
    // This may need to be async function() if there needs to be an await this._rpc({ ... }); call to not reload early
    _onGetPartnerClick: function () {
        this._rpc({
            model: 'res.partner',
            method: 'get_odoo_partner',
            args: [],
        }).then(() => {
            this.reload();
        });
        // Couldn't test this for real, but it runs the action. May need a this.reload()
    },
});

export const OdooScrapperKanbanView = KanbanView.extend({
    config: _.extend({}, KanbanView.prototype.config, {
        Controller: OdooScrapperKanbanController,
    }),
});

// key must match with the js_class attribute of the tree view you want to modify
viewRegistry.add('res_partner_odoo_scrapper_kanban', OdooScrapperKanbanView);



