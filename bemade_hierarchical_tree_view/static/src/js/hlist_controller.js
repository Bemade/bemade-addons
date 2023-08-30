/** @odoo-module alias=htree.HListController **/

import ListController from 'web.ListController';

var HListController = ListController.extend({
    custom_events: _.extend({}, ListController.prototype.custom_events, {
        toggle_hierarchy: '_onToggleHierarchy'
    }),
    init: function(parent, model, renderer, params) {
      this._super.apply(this, arguments);
    },
    _onToggleHierarchy: function(ev) {

    },
})