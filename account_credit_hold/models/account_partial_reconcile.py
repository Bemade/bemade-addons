from odoo import models


class AccountPartialReconcile(models.Model):
    """Re-evaluate the credit hold when a reconciliation is undone.

    Matching itself is caught by the ``_reconcile_plan`` hook on
    ``account.move.line``; this covers the reverse (a bounced cheque, a
    reversed payment). Un-matching re-opens the debt, so the evaluator will
    simply find the hold still warranted and leave it alone -- events never
    place a hold, only release one.
    """

    _inherit = "account.partial.reconcile"

    def unlink(self):
        # Queue before the rows disappear so the partners are still readable.
        lines = self.debit_move_id | self.credit_move_id
        partners = lines.partner_id
        if partners:
            partners._queue_credit_hold_release()
        return super().unlink()
