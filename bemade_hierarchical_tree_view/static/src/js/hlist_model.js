/** @odoo-module alias=htree.HListModel **/

import ListModel from 'web.ListModel'

var HListModel = ListModel.extend({
    /**
     * @override
     * @param {string} params.parentField
     */
    init: function (parent, params) {
        var self = this;
        this._super.apply(this, arguments);
        self.parentField = params.parentField;
        self.loadParams.domain = _.union(self.loadParams.domain,
            [[self.parentField, '=', false]])
    },
})

export default HListModel;