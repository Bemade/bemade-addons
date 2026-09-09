from odoo import models


class AccountMove(models.Model):
    """Release credit holds when the ledger changes under a held customer.

    Covers the two cases reconciliation alone misses:

      * a payment is recorded but not yet matched -- it still posts an
        unreconciled receivable line, which already lowers the partner's
        residual and can drop them below a hold-bearing follow-up level;
      * an overdue invoice is cancelled or reset to draft.

    Like every event hook here this only ever releases; placing a hold stays
    with the follow-up run so the customer is told about it.
    """

    _inherit = "account.move"

    def _post(self, soft=True):
        posted = super()._post(soft=soft)
        posted._credit_hold_queue_partners()
        return posted

    def button_draft(self):
        res = super().button_draft()
        self._credit_hold_queue_partners()
        return res

    def button_cancel(self):
        res = super().button_cancel()
        self._credit_hold_queue_partners()
        return res

    def _credit_hold_queue_partners(self):
        partners = self.partner_id
        if partners:
            partners._queue_credit_hold_release()
