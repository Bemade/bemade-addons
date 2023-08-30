/** @odoo-module alias=htree.HListModel **/

import ListModel from 'web.ListModel'

var HListModel = ListModel.extend({
    /**
     * @override
     * @param {string} params.parentField
     */
    init: function (parent, params) {
        this._super.apply(this, arguments);
        this.parentField = params.parentField;
    },
    /**
     *
     * @override
     * @private
     */
    _readGroup: function (list, options) {
       var self = this;
       return this._super(list, options).then(function (result) {
          return self._readHierarchy(list).then(_.constant(result));
       });
    },
    /**
     * Fetches hierarchy specific fields on the parent field relation and stores them
     * in the column datapoint in a special key 'hierarchyData'.
     * Data for the hierarchy are fetched in batch for all hierarchies, to avoid
     * multiple calls.
     *
     * @param {Object} list
     * @private
     * @returns {Promise}
     */
    _readHierarchy (list) {
        const self = this;
        const parentFieldName = self.parentField;
        const parentField = list.fields[parentFieldName];
        /* Each record should have only one parent */
        if (parentField.type !== 'many2one') {
            return Promise.resolve();
        }
        const hierarchyIds = _.reduce(list.data, function (hierarchyIds, id) {
           const resId = self.get(id, { raw: true }).res_id;
           if (resId) {
               hierarchyIds.push(resId);
           }
           return hierarchyIds;
        }, []);
        let prom;
        if (hierarchyIds.length) {
            prom = this._rpc({
                model: list.model,
                method: 'read',
                args: [hierarchyIds, self.viewFields],
                context: list.context,
            });
        }
        return Promise.resolve(prom).then(function (result) {
            _.each(list.data, function(id) {
                let dp = self.localData[id];
                let hierarchyData = result && _.findWhere(result, {
                    id: dp.res_id,
                });
                let hierarchyDp = self._makeDataPoint({
                    context: dp.context,
                    data: hierarchyData,
                    fields: list.fields,
                    fieldsInfo: list.fieldsInfo,
                    modelName: list.model,
                    parentID: dp.id,
                    res_id: dp.res_id,
                    viewType: 'list',
                });
            });
        });
    },
})

export default HListModel;