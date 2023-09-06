/** @odoo-module alias=htree.HListRenderer **/

import {ListRenderer} from 'web.ListRenderer'

const toggleClass = 'o_hlist_toggle';
const toggleIconClass = 'fa-sitemap';

var HierarchicalListRenderer = ListRenderer.extend({
    className: 'o_hlist_view',
    events: _.extend({}, ListRenderer.prototype.events, {
        'click o_hlist_toggle': '_onToggleHierarchyGroup',
    }),
    /**
     * @param {string} params.parentField
     * @param {string} params.childrenField
     */
    init: function (parent, state, params) {
        this._super.apply(this, arguments);

        this.parentField = params.parentField;
        this.childrenField = params.childrenField;
    }, // TODO: add header column on left side for toggle
    /**
     * @override
     * @private
     * @param {Object} record
     * @returns {jQueryElement} a <tr> element
     */
    _renderRow: function (record) {
        var self = this;
        var $tr = this._super.apply(this, arguments)
        if (this.childrenField in record.data) {
            let numChildren = record.data[this.childrenField].length
            if (numChildren > 0) {
                $td = $('<td>', {class: toggleClass}).append(
                    $('<span>', {class: toggleIconClass, text: numChildren})
                )
            } else {
                $tr.prepend($('<td>'))
            }
        }
        if (record.data.child_ids && record.data.child_ids.length) {
            $tr.prepend(this._renderHierarchyToggle(record));
        } else {
            $tr.prepend($('<td>'))
        }
    },
    /**
     *
     * @param record
     * @private
     * @returns {jQueryElement} a <td> element
     */
    _renderHierarchyToggle: function (record) {
        let numChildren = record.data[this.childrenField].length

    }
})