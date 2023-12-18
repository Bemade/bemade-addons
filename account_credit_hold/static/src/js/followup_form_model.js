/** @odoo-module **/

var FollowupFormModel = require('account_followup.FollowupFormModel');
import { patch } from '@web/core/utils/patch';

var PatchedModel = patch(FollowupFormModel.prototype, 'followup_form_model', {
    doCreditHold: function(handle) {
        var level = this.localData[handle].data.followup_level;
        if(level && level.credit_hold) {
            level.credit_hold = false;
        }
    },
});
export { PatchedModel };