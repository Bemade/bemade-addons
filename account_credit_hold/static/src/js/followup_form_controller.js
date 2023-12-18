/** @odoo-module **/

var FollowupFormController = require('account_followup.FollowupFormController');
import { patch } from '@web/core/utils/patch';

var PatchedController = patch(FollowupFormController.prototype, "followup_form_controller", {
    events: _.extend({}, FollowupFormController.prototype.events, {
        'click .o_account_followup_credit_hold_button': '_onCreditHold',
    }),
    updateButtons() {
        this._super(...arguments);
        let setButtonClass = (button, primary) => {
            /* Set class 'btn-primary' if parameter `primary` is true
             * 'btn-secondary' otherwise
             */
            let addedClass = primary ? 'btn-primary' : 'btn-secondary'
            let removedClass = !primary ? 'btn-secondary' : 'btn-primary'
            this.$buttons.find(`button.${button}`)
                .removeClass(removedClass).addClass(addedClass);
        }
        if (!this.$buttons) {
            return;
        }
        let followupLevel = this.model.localData[this.handle].data.followup_level;
        setButtonClass('o_account_followup_credit_hold_button', followupLevel.credit_hold);
    },
    _onCreditHold: function() {
      var self = this;
      this.model.doCreditHold(this.handle);
      this.options = {
          partner_id: this._getPartner()
      };
      this._rpc({
          model: 'account.followup.report',
          method: 'credit_hold',
          args: [this.options],
      }).then(function (result) {
          self._removeHighlightCreditHold();
          self._displayDone();
      });
    },
    _removeHighlightCreditHold: function() {
        this.$buttons.find('button.o_account_followup_credit_hold_button')
            .removeClass('btn-primary').addClass('btn-secondary');
    },
});

export { PatchedController };