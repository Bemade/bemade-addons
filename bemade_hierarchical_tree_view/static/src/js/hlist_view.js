/** @odoo-module alias=htree.HListView **/

/**
 * The Hierarchical List view extends the base List View from Odoo by adding
 * a toggle to expand/collapse a hierarchy of records with children.
 */

import ListView from 'web.ListView';
import viewRegistry from 'web.view_registry';
import HListRenderer from 'htree.HListRenderer';
import HListController from 'htree.HListController';
import HListModel from 'htree.HListModel';


var HListView = ListView.extend({
    accesskey: 't',
    icon: 'fa-sitemap',
    display_name: _lt("Hierarchical Tree"),
    config: _.extend({}, ListView.prototype.config, {
        Model: HListModel,
        Controller: HListController,
        Renderer: HListRenderer,
    }),
    viewType: 'hlist',
    /**
     * Add a parentField parameter to allow for hierarchy display.
     *
     * @override
     *
     * @param {Object} viewInfo
     * @param {Object} params
     * @param {boolean} params.hasActionMenus
     * @param {string} [params.parentField]
     * @param {boolean} [params.hasSelectors=true]
     */
    init: function(viewInfo, params) {
        var self = this;
        this._super.apply(this, arguments);
        this.parentField = params.parentField
    },
    _updateMVCParams: function() {
        this._super.apply(this, arguments);
        var attrs = this.arch.attrs;
        this.loadParams.parentField = attrs.parentField;
        this.modelParams.parentField = attrs.parentField;
    }
});

viewRegistry.add('hlist', HListView);
