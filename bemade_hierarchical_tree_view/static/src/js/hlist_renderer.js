/** @odoo-module alias=htree.HListRenderer **/

import {ListRenderer} from 'web.ListRenderer'

var HierarchicalListRenderer = ListRenderer.extend({
    className: 'o_hlist_view',
    events: _.extend({}, ListRenderer.prototype.events, {
        'click .o_hierarchy_parent': '_onToggleHierarchyGroup',
    }),
    init: function (parent, state, params) {
        this._super.apply(this, arguments);
    },
    _renderBody: function () {
        this._super.apply(this);

    },
    _renderHierarchy(data, hierarchyLevel) {
        var self = this;
        hierarchyLevel = hierarchyLevel || 0;
        var result = [];
        var $tbody = $('<tbody>');
        _.each(data, function (hierarchyGroup) {
            if (!$tbody) {
                $tbody = $('<tbody>');
            }
            $tbody.append(self._renderHierarchyRow(hierarchyGroup, hierarchyLevel));
            if (hierarchyGroup.data.length) {
                result.push($tbody);
                result = result.concat(self._renderHierarchyParent(hierarchyGroup,
                    hierarchyLevel));
                $tbody = null;
            }
        })
    },
    _renderHierarchyParent(hierarchyGroup, hierarchyLevel) {

    }
})