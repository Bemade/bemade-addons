from odoo import api, models


class AccountMoveLine(models.Model):
    """Release credit holds when a customer's balance is actually settled.

    ``_reconcile_plan`` is the single funnel every reconciliation flow goes
    through in Odoo 18 (``reconcile()`` calls it, so does the bank
    reconciliation widget and the payment matching), which makes it the one
    place worth hooking rather than chasing each caller.

    Note that ``account.payment`` deliberately has NO hook of its own. The
    payment record is inert as far as credit hold is concerned: moving it to
    ``in_process``/``paid`` generates and posts its journal entry, and it is
    the reconciliation of that entry against the invoice that clears the
    receivable. Registering a payment therefore releases a hold immediately,
    before the bank reconciliation -- the invoice drops to a zero residual and
    sits at ``in_payment`` -- but it does so through this hook, not through
    anything on the payment itself.
    """

    _inherit = "account.move.line"

    @api.model
    def _reconcile_plan(self, reconciliation_plan):
        res = super()._reconcile_plan(reconciliation_plan)
        amls = self.browse()
        for group in reconciliation_plan:
            # A plan entry is either a recordset of amls or a nested plan.
            if isinstance(group, models.BaseModel):
                amls |= group
            else:
                for nested in group:
                    if isinstance(nested, models.BaseModel):
                        amls |= nested
        partners = amls.partner_id
        if partners:
            partners._queue_credit_hold_release()
        return res
