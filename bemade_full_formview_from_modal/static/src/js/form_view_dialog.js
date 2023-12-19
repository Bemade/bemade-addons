/** @odoo-module **/

import FormViewDialog from 'web.FormView';
import Dialog from 'web.Dialog';
import {patch} from '@web/core/utils/patch';
import {_t} from 'web.core';

const dom = require('web.dom')

patch(Dialog.prototype, "bemade_full_formview_from_modal.Dialog", {
    init: function (parent, options) {
        this._super(...arguments);
    },
    willStart: function () {
        const self = this;
        return this._super(...arguments).then(function () {
                if (self.$footer) {
                    const $button = dom.renderButton({
                        attrs: {
                            class: 'btn btn-secondary o_form_button_open',
                        },
                        text: _t('Open'),
                    });
                    $button.on('click', function() {self._onOpen.call(self)});
                    self.$footer.append($button);
                }
            }
        );
    },
    _onOpen: function () {
        this.do_action({
            type: 'ir.actions.act_window',
            res_model: this.options.res_model,
            res_id: this.options.res_id,
            views: [[false, 'form']],
            target: 'current',
            context: this.context,
        })
    }
});
