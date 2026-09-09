import operator as _op
from collections import defaultdict
from datetime import date

from odoo import fields, models, api, _


class Partner(models.Model):
    _inherit = "res.partner"

    postpone_hold_until = fields.Date(
        string="Postpone Hold",
        help="Grace period specific to this partner despite unpaid invoices.",
        tracking=True,
    )

    # Canonical "should this client be on hold, ignoring postponements".
    #
    # Deliberately NOT a computed field. It is a state, set and cleared by
    # explicit transitions (see the credit-hold evaluation section below), so
    # that a postponed hold stays visible and so that the value does not
    # depend on who happened to read which field. It used to be
    # compute+store off the non-stored ``followup_status``, which meant it was
    # only ever re-derived as a side effect of reading that field.
    hold_bg = fields.Boolean(
        string="Hold (technical)",
        default=False,
        tracking=True,
        copy=False,
    )
    on_hold = fields.Boolean(
        string="Account on Hold",
        help="Client account is on hold for unpaid overdue invoices.",
        compute="_compute_on_hold",
        compute_sudo=True,
        search="_search_on_hold",
    )
    # Upstream account_followup defines total_due as a non-stored Monetary
    # without a search method, which makes modern Odoo's view validator reject
    # the "Overdue Invoices" filter (domain=[('total_due','>',0)]) in
    # views/res_partner_views.xml. Add a search driver here — keeps the field
    # non-stored as upstream intends.
    total_due = fields.Monetary(search="_search_total_due")

    def _search_on_hold(self, operator, value):
        """Search-driver for the non-stored `on_hold` field.

        Mirrors the truth table in ``_compute_on_hold``:

          on_hold = True  iff
              (self.commercial_partner_id has hold_bg=True and no active postpone)
           OR (self.hold_bg=True and no active postpone on self)

        We resolve to a set of ids and return an ``('id', 'in', ...)`` domain.
        """
        if operator not in ("=", "!=") or not isinstance(value, bool):
            raise NotImplementedError(
                _("Unsupported operator %r for on_hold search.") % operator
            )
        today = date.today()
        # Partners whose own hold_bg is on with no active postpone.
        held_directly = self.with_context(active_test=False).search([
            ("hold_bg", "=", True),
            "|",
            ("postpone_hold_until", "=", False),
            ("postpone_hold_until", "<=", today),
        ])
        # Plus any partner whose commercial_partner_id is in that held set
        # (covers sub-contacts inheriting hold from their commercial entity).
        held_via_commercial = self.with_context(active_test=False).search([
            ("commercial_partner_id", "in", held_directly.ids),
        ])
        held_ids = (held_directly | held_via_commercial).ids
        is_match = value if operator == "=" else not value
        return [("id", "in" if is_match else "not in", held_ids)]

    def _search_total_due(self, operator, value):
        """Search-driver for the non-stored upstream `total_due` Monetary.

        Aggregates posted unreconciled receivable AMLs per partner (same
        domain ``_compute_total_due`` uses upstream) and applies the
        comparison. Partners with no matching AMLs (total_due == 0) are
        included if 0 satisfies the operator.
        """
        op_func_map = {
            "=": _op.eq,
            "!=": _op.ne,
            ">": _op.gt,
            "<": _op.lt,
            ">=": _op.ge,
            "<=": _op.le,
        }
        if operator not in op_func_map:
            raise NotImplementedError(
                _("Unsupported operator %r for total_due search.") % operator
            )
        op_func = op_func_map[operator]
        aml_groups = self.env["account.move.line"]._read_group(
            domain=[
                ("reconciled", "=", False),
                ("account_id.account_type", "=", "asset_receivable"),
                ("parent_state", "=", "posted"),
            ],
            groupby=["partner_id"],
            aggregates=["amount_residual:sum"],
        )
        explicit_match = {p.id for p, total in aml_groups if op_func(total, value)}
        explicit_partners = {p.id for p, _ in aml_groups}
        # If 0 satisfies the operator, partners with no AMLs (implicit total 0)
        # should also match — express that as a "not in" on the partners that
        # explicitly do NOT match.
        if op_func(0.0, value):
            return [("id", "not in", list(explicit_partners - explicit_match))]
        return [("id", "in", list(explicit_match))]

    @api.depends("postpone_hold_until", "hold_bg", "commercial_partner_id.hold_bg")
    def _compute_on_hold(self):
        for rec in self:
            # If the parent company is on hold, so are all its sub-contacts and subsidiaries
            if rec.commercial_partner_id != rec and rec.commercial_partner_id.hold_bg:
                if not (
                    rec.commercial_partner_id.postpone_hold_until
                    and rec.commercial_partner_id.postpone_hold_until > date.today()
                ):
                    rec.on_hold = True
                    continue

            # If there is no parent company or the parent is not on hold, we compute for ourselves
            if rec.hold_bg and not (
                rec.postpone_hold_until and rec.postpone_hold_until > date.today()
            ):
                rec.on_hold = True
            else:
                rec.on_hold = False

    @api.autovacuum
    def _cleanup_expired_hold_postponements(self):
        expired_holds = self.search([("postpone_hold_until", "<=", date.today())])
        expired_holds.write({"postpone_hold_until": False})

    def action_credit_hold(self):
        # Idempotent: only a real transition is worth a chatter entry. The
        # follow-up run and the event hooks both call this unconditionally.
        for rec in self:
            if rec.hold_bg:
                continue
            rec.hold_bg = True
            rec.message_post(body=_("Placed on credit hold."))

    def action_lift_credit_hold(self):
        for rec in self:
            if not rec.hold_bg:
                continue
            rec.hold_bg = False
            rec.message_post(body=_("Credit hold lifted."))

    @api.model
    def _get_first_followup_level(self):
        return self.env["account_followup.followup.line"].search(
            [("company_id", "parent_of", self.env.company.id)],
            order="delay asc",
            limit=1,
        )

    # ------------------------------------------------------------------
    # Credit hold evaluation
    #
    # Placement and release are deliberately asymmetric:
    #
    #   * Follow-ups PLACE a hold. Manual and automatic follow-ups both funnel
    #     through ``_execute_followup_partner``. A hold blocks the customer
    #     from confirming sales orders, so it stays tied to the dunning run
    #     that also emails them about it -- nothing gets blocked silently.
    #
    #   * Account events RELEASE a hold, and never place one. Recording a
    #     payment is when a customer expects to be unblocked; waiting for the
    #     nightly run is too slow.
    #
    #   * The cron sweep is the backstop for the only transition that emits no
    #     event at all: an invoice quietly ageing past a hold-bearing level.
    # ------------------------------------------------------------------

    _CREDIT_HOLD_QUEUE = "account_credit_hold.pending_release"

    def _queue_credit_hold_release(self):
        """Queue partners for a release check at the end of the transaction.

        Batched through ``cr.precommit`` so that a bank-statement run
        reconciling hundreds of lines evaluates once rather than per line, and
        only after every write has landed -- ``amount_residual`` is not final
        until then.
        """
        # Events only ever release, so partners that are not held are of no
        # interest. This is what keeps mass reconciliation cheap.
        candidates = self.filtered(
            lambda p: p.hold_bg or p.commercial_partner_id.hold_bg
        )
        if not candidates:
            return
        # ``on_hold`` is inherited from the commercial entity, so a payment
        # landing on a child contact has to re-evaluate the parent.
        candidates |= candidates.commercial_partner_id

        precommit = self.env.cr.precommit
        pending = precommit.data.get(self._CREDIT_HOLD_QUEUE)
        if pending is None:
            pending = precommit.data[self._CREDIT_HOLD_QUEUE] = set()
            precommit.add(
                self.env["res.partner"].sudo()._run_queued_credit_hold_release
            )
        for partner in candidates:
            # The follow-up query is company-scoped, so remember which company
            # each partner was touched in.
            company = partner.company_id or self.env.company
            pending.add((partner.id, company.id))

    def _run_queued_credit_hold_release(self):
        """Drain the queue registered by :meth:`_queue_credit_hold_release`."""
        pending = self.env.cr.precommit.data.pop(self._CREDIT_HOLD_QUEUE, None)
        if not pending:
            return
        by_company = defaultdict(list)
        for partner_id, company_id in pending:
            by_company[company_id].append(partner_id)
        for company_id, partner_ids in by_company.items():
            partners = self.browse(partner_ids).exists()
            if partners:
                partners.with_company(company_id)._evaluate_credit_hold_release()

    def _evaluate_credit_hold_release(self):
        """Lift the hold on partners the follow-up sequence no longer warrants.

        Release only -- this never places a hold. Returns the partners
        released.
        """
        # ``_query_followup_data`` memoises its expensive query on the cursor
        # for the whole transaction. By the time this runs, reconciliations in
        # that same transaction have changed the answer, so the cached copy is
        # pre-payment data. Without dropping it the check silently concludes
        # that nothing changed -- no error, just a hold that never lifts.
        self.env.cr.cache.pop("res_partner_all_followup", None)
        self.invalidate_recordset()

        to_release = self.filtered(
            lambda p: p.hold_bg and not p._should_hold_any_company()
        )
        if to_release:
            to_release.action_lift_credit_hold()
        return to_release

    def _cron_execute_followup_company(self):
        # Backstop. Upstream computes follow-up data for every partner here and
        # then narrows to the ones it will email, so it never visits partners
        # that are paid up, merely "with overdue invoices", or on manual
        # reminders -- which are exactly the ones whose hold needs clearing.
        held = self.env["res.partner"].search([("hold_bg", "=", True)])
        if held:
            held._evaluate_credit_hold_release()
        return super()._cron_execute_followup_company()

    def _execute_followup_partner(self, options=None):
        # Check if we need to place on credit hold before expensive operations
        should_hold = self._should_hold()

        # If this is just for credit hold and we don't need reports/emails, skip heavy operations
        if options and options.get("credit_hold_only"):
            self._apply_followup_credit_hold(should_hold)
            return should_hold

        # Otherwise run the full followup process
        res = super()._execute_followup_partner(options)

        # Apply credit hold after successful followup execution
        self._apply_followup_credit_hold(should_hold)
        if should_hold:
            res = True

        return res

    def _apply_followup_credit_hold(self, should_hold):
        """Set hold state from a follow-up run -- manual or automatic.

        The follow-up run is the authoritative evaluation of the dunning
        sequence, so it both places a hold the sequence warrants and clears one
        it no longer does. This is the only path allowed to PLACE a hold, so
        that a customer blocked from ordering has always been told why.
        """
        if should_hold:
            self.action_credit_hold()
        else:
            self.action_lift_credit_hold()

    @api.depends("unreconciled_aml_ids", "followup_next_action_date")
    @api.depends_context("company", "allowed_company_ids")
    def _compute_followup_status(self):
        # This override exists ONLY to widen the dependency set with
        # depends_context. It must not touch credit-hold state: releasing a
        # hold from inside a compute made the release fire on every read of a
        # non-stored field, so a hold survived only until somebody happened to
        # open the record -- and the sales-order block ran off the stale flag
        # in the meantime. Release now happens on real account events; see
        # _queue_credit_hold_release above.
        return super()._compute_followup_status()

    def _should_hold(self):
        self.ensure_one()
        return self.followup_line_id and self.followup_line_id.account_hold

    def _should_hold_any_company(self):
        """Whether a hold is warranted in ANY company that could hold this partner.

        ``_should_hold`` reads company-scoped follow-up state (``followup_line_id``
        is computed with ``depends_context("company", ...)``), so it only ever
        answers for ``self.env.company``. A hold placed on the strength of one
        company's receivables must not be released just because a *different*
        company's sweep happens to run next -- see
        ``_evaluate_credit_hold_release``, which is invoked once per company by
        both the release-precommit queue and upstream's per-company cron loop.

        A partner with its own ``company_id`` is scoped to that one company. A
        shared partner (``company_id`` unset) can be held on the strength of
        receivables in any company, so all companies must clear before release.
        """
        self.ensure_one()
        companies = self.company_id or self.env["res.company"].search([])
        return any(self.with_company(company)._should_hold() for company in companies)
