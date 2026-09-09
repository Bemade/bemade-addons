# -*- coding: utf-8 -*-
"""Credit hold is placed by follow-ups and released by account events.

These pin the asymmetry the module relies on:

  * reading a field must NEVER change hold state (the defect this replaces --
    the release used to run inside ``_compute_followup_status``, so a hold
    lasted only until somebody opened the record);
  * settling the balance releases promptly, without waiting for the cron;
  * events must never PLACE a hold, or a customer gets blocked from
    confirming sales orders with no notification.
"""

from odoo import Command, fields
from odoo.tests import common, tagged


@tagged("post_install", "-at_install")
class TestCreditHoldReevaluation(common.TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({
            "name": "Reevaluation Customer",
            "is_company": True,
            "customer_rank": 1,
            "email": "reeval@example.com",
        })
        cls.env["account_followup.followup.line"].search([]).unlink()
        cls.line_soft = cls.env["account_followup.followup.line"].create({
            "company_id": cls.env.company.id,
            "name": "Soft",
            "delay": 15,
            "account_hold": False,
            "send_email": True,
        })
        cls.line_hold = cls.env["account_followup.followup.line"].create({
            "company_id": cls.env.company.id,
            "name": "Hold",
            "delay": 30,
            "account_hold": True,
            "send_email": True,
        })

    def _overdue_invoice(self, days, amount=1000.0):
        due = fields.Date.today() - fields.date_utils.relativedelta(days=days)
        invoice = self.env["account.move"].create({
            "partner_id": self.partner.id,
            "move_type": "out_invoice",
            "invoice_date": due,
            "invoice_date_due": due,
            "invoice_line_ids": [Command.create({
                "name": "Service",
                "quantity": 1.0,
                "price_unit": amount,
            })],
        })
        invoice.action_post()
        return invoice

    def _put_on_hold_level(self):
        """Advance the partner to the hold-bearing follow-up level.

        A newly overdue invoice enters at the FIRST level whatever its age --
        upstream advances one level per reminder sent -- so reaching the hold
        level in a test means saying so. ``followup_line_id`` has an inverse
        that stamps the underlying journal items.
        """
        self.partner.followup_line_id = self.line_hold

    def _settle(self, invoice):
        """Fully settle an invoice through the real reconciliation funnel."""
        refund = self.env["account.move"].create({
            "partner_id": self.partner.id,
            "move_type": "out_refund",
            "invoice_date": fields.Date.today(),
            "invoice_line_ids": [Command.create({
                "name": "Settlement",
                "quantity": 1.0,
                "price_unit": invoice.amount_total,
            })],
        })
        refund.action_post()
        receivable = (invoice.line_ids | refund.line_ids).filtered(
            lambda line: line.account_id.account_type == "asset_receivable"
        )
        receivable.reconcile()
        return refund

    def _n_lifts(self):
        return self.env["mail.message"].search_count([
            ("res_id", "=", self.partner.id),
            ("model", "=", "res.partner"),
            ("body", "ilike", "Credit hold lifted"),
        ])

    # ------------------------------------------------------------------
    # Reading must not mutate hold state
    # ------------------------------------------------------------------

    def test_reading_followup_status_does_not_release_hold(self):
        """The regression this redesign exists for.

        A held customer who still owes money must stay held when their
        follow-up status is merely read. Previously each read released the
        hold, wrote to the database and posted to the chatter.
        """
        self._overdue_invoice(days=40)
        self._put_on_hold_level()
        self.partner.action_credit_hold()
        self.assertTrue(self.partner.on_hold)

        for _ in range(5):
            self.partner.invalidate_recordset()
            self.partner.mapped("followup_status")   # the read is the point

        self.assertTrue(
            self.partner.hold_bg,
            "Reading followup_status must not release a credit hold.",
        )
        self.assertEqual(
            self._n_lifts(), 0,
            "Reading a field must not post 'Credit hold lifted' to the chatter.",
        )

    def test_reading_does_not_release_even_below_hold_level(self):
        """Even when the rule no longer warrants the hold, a READ must not act.

        The release is legitimate here, but it belongs to an account event or
        the cron -- not to whoever happens to open the record. This is what
        keeps the sales-order block deterministic.
        """
        self._overdue_invoice(days=20)          # lands on the non-hold level
        self.partner.action_credit_hold()

        self.partner.invalidate_recordset()
        self.partner.mapped("followup_status")

        self.assertTrue(self.partner.hold_bg)
        self.assertEqual(self._n_lifts(), 0)

    # ------------------------------------------------------------------
    # Events release
    # ------------------------------------------------------------------

    def test_paying_the_invoice_releases_the_hold(self):
        """Settling the balance releases without waiting for the cron."""
        invoice = self._overdue_invoice(days=40)
        self._put_on_hold_level()
        self.partner.action_credit_hold()
        self.assertTrue(self.partner.on_hold)

        self._settle(invoice)
        # The hook queues the release; the cursor drains it on flush.
        self.env.cr.flush()
        self.partner.invalidate_recordset()

        self.assertFalse(
            self.partner.hold_bg,
            "Paying the overdue invoice should release the credit hold.",
        )
        self.assertEqual(self._n_lifts(), 1)

    def test_release_is_batched_once_per_transaction(self):
        """Many reconciliations in one transaction evaluate once, not per line."""
        invoices = [self._overdue_invoice(days=40) for _ in range(3)]
        self._put_on_hold_level()
        self.partner.action_credit_hold()

        for invoice in invoices:
            self._settle(invoice)

        self.env.cr.flush()
        self.partner.invalidate_recordset()

        self.assertFalse(self.partner.hold_bg)
        self.assertEqual(
            self._n_lifts(), 1,
            "The hold should be released once, not once per reconciliation.",
        )

    def test_registering_a_payment_releases_the_hold(self):
        """Recording a payment releases immediately, before bank reconciliation.

        Registering a customer payment posts its journal entry and reconciles
        the invoice against the outstanding-receipts account there and then --
        the invoice drops to a zero residual and sits at ``in_payment`` until
        the bank statement clears it. The debt is already gone from the
        customer's ledger at that point, so the hold goes with it rather than
        waiting for the bank rec or the nightly run.
        """
        journal = self.env["account.journal"].search(
            [("type", "=", "bank"), ("company_id", "=", self.env.company.id)],
            limit=1,
        )
        method_line = journal.inbound_payment_method_line_ids[:1]
        self.assertTrue(method_line, "bank journal needs an inbound method line")
        if not method_line.payment_account_id:
            # A real chart template supplies this; the test company does not,
            # and without it no journal entry is generated at all.
            method_line.payment_account_id = self.env["account.account"].create({
                "name": "Outstanding Receipts (test)",
                "code": "ZZOUT1",
                "account_type": "asset_current",
                "reconcile": True,
            })

        invoice = self._overdue_invoice(days=40)
        self._put_on_hold_level()
        self.partner.action_credit_hold()
        self.assertTrue(self.partner.on_hold)

        self.env["account.payment.register"].with_context(
            active_model="account.move", active_ids=invoice.ids,
        ).create({})._create_payments()

        self.env.cr.flush()
        self.env.invalidate_all()

        self.assertEqual(
            invoice.amount_residual, 0.0,
            "Registering the payment should clear the receivable.",
        )
        self.assertFalse(
            self.partner.hold_bg,
            "Recording a payment should release the hold without waiting for "
            "the bank reconciliation.",
        )

    # ------------------------------------------------------------------
    # Events must never place
    # ------------------------------------------------------------------

    def test_posting_an_overdue_invoice_does_not_place_a_hold(self):
        """Events release only.

        A hold blocks sale order confirmation, so it must never appear as a
        side effect of bookkeeping -- only from a follow-up run, which tells
        the customer.
        """
        self.assertFalse(self.partner.hold_bg)
        self._overdue_invoice(days=40)          # squarely on the hold level
        self.env.cr.flush()

        self.assertFalse(
            self.partner.hold_bg,
            "Posting an invoice must not silently place a credit hold.",
        )

    def test_unreconciling_does_not_place_a_hold(self):
        """A reversed payment re-opens the debt but must not re-block silently."""
        invoice = self._overdue_invoice(days=40)
        self.env["account.payment.register"].with_context(
            active_model="account.move", active_ids=invoice.ids,
        ).create({})._create_payments()
        self.env.cr.flush()
        self.assertFalse(self.partner.hold_bg)

        invoice.line_ids.filtered(
            lambda line: line.account_id.account_type == "asset_receivable"
        ).remove_move_reconcile()
        self.env.cr.flush()

        self.assertFalse(
            self.partner.hold_bg,
            "Un-reconciling must not place a hold; that is the follow-up's job.",
        )

    # ------------------------------------------------------------------
    # Follow-ups place; the cron sweeps
    # ------------------------------------------------------------------

    def test_followup_execution_places_the_hold(self):
        """Both manual and automatic follow-ups run through this method."""
        self._overdue_invoice(days=40)
        self._put_on_hold_level()
        self.assertFalse(self.partner.hold_bg)

        self.partner._execute_followup_partner(options={"credit_hold_only": True})

        self.assertTrue(
            self.partner.hold_bg,
            "A follow-up on a hold-bearing level should place the hold.",
        )

    def test_cron_sweep_releases_partners_the_send_loop_never_visits(self):
        """The backstop.

        The cron only emails partners that are ``in_need_of_action`` with an
        auto-executing level. A customer who has paid up is never visited by
        that loop, so without the sweep their hold would never clear.
        """
        self.partner.action_credit_hold()
        self.assertTrue(self.partner.hold_bg)
        # No overdue invoice at all -> no follow-up level -> no hold warranted,
        # and nothing for the send loop to do.
        self.env["res.partner"]._cron_execute_followup_company()

        self.assertFalse(
            self.partner.hold_bg,
            "The cron sweep should clear holds the send loop never visits.",
        )

    # ------------------------------------------------------------------
    # Postponement is orthogonal
    # ------------------------------------------------------------------

    def test_postponement_hides_the_hold_without_clearing_it(self):
        """``hold_bg`` is the canonical state; ``on_hold`` applies the grace."""
        self._overdue_invoice(days=40)
        self._put_on_hold_level()
        self.partner.action_credit_hold()

        self.partner.postpone_hold_until = (
            fields.Date.today() + fields.date_utils.relativedelta(days=7)
        )

        self.assertTrue(
            self.partner.hold_bg,
            "A postponement must not clear the underlying hold.",
        )
        self.assertFalse(
            self.partner.on_hold,
            "A postponement should suppress the effective hold.",
        )


@tagged("post_install", "-at_install")
class TestCreditHoldMultiCompanyRelease(common.TransactionCase):
    """``_evaluate_credit_hold_release`` runs once PER COMPANY -- both the
    18.0.1.2.0 migration and upstream's ``_cron_execute_followup_company``
    loop invoke it via ``with_company(company)``. A hold warranted by one
    company's receivables must not be released just because a *different*
    company's sweep happens to run.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.company_a = cls.env.company
        cls.company_b = cls.env["res.company"].create({"name": "Credit Hold Co B"})

        cls.env["account_followup.followup.line"].search([
            ("company_id", "in", (cls.company_a | cls.company_b).ids),
        ]).unlink()
        cls.line_hold_a = cls.env["account_followup.followup.line"].create({
            "company_id": cls.company_a.id,
            "name": "Hold A",
            "delay": 30,
            "account_hold": True,
            "send_email": True,
        })
        cls.line_soft_b = cls.env["account_followup.followup.line"].create({
            "company_id": cls.company_b.id,
            "name": "Soft B",
            "delay": 15,
            "account_hold": False,
            "send_email": True,
        })

        # A shared partner (no company_id of its own) can be held on the
        # strength of receivables in any company it does business with.
        cls.partner = cls.env["res.partner"].create({
            "name": "Shared Multi-Company Customer",
            "is_company": True,
            "customer_rank": 1,
            "email": "shared-multico@example.com",
        })

    def _overdue_invoice(self, company, days=40, amount=1000.0):
        due = fields.Date.today() - fields.date_utils.relativedelta(days=days)
        invoice = self.env["account.move"].with_company(company).create({
            "partner_id": self.partner.id,
            "move_type": "out_invoice",
            "invoice_date": due,
            "invoice_date_due": due,
            "invoice_line_ids": [Command.create({
                "name": "Service",
                "quantity": 1.0,
                "price_unit": amount,
            })],
        })
        invoice.action_post()
        return invoice

    def test_hold_warranted_in_one_company_survives_release_in_another(self):
        """The fix's regression: fails on the single-company release, passes after.

        The receivable and the hold-bearing level both live in company A.
        Evaluating the release from company B's context must not clear it --
        company B has no unpaid receivable to be lenient about; it simply has
        no say over a debt it never saw.
        """
        self._overdue_invoice(self.company_a, days=40)
        self.partner.with_company(self.company_a).followup_line_id = (
            self.line_hold_a
        )
        self.partner.with_company(self.company_a).action_credit_hold()
        self.assertTrue(self.partner.hold_bg)

        self.partner.with_company(self.company_b)._evaluate_credit_hold_release()

        self.assertTrue(
            self.partner.hold_bg,
            "A hold warranted by company A's receivables must survive a "
            "release sweep run in company B's context.",
        )

    def test_hold_unwarranted_in_any_company_is_still_released(self):
        """Guard against over-correcting: a genuinely stale hold still clears.

        No overdue receivable anywhere, so ``_should_hold_any_company`` must
        find nothing warranting the hold in either company and release it --
        proving the fix does not turn the sweep into a no-op.
        """
        self.partner.action_credit_hold()
        self.assertTrue(self.partner.hold_bg)

        released = self.partner.with_company(
            self.company_b
        )._evaluate_credit_hold_release()

        self.assertEqual(released, self.partner)
        self.assertFalse(
            self.partner.hold_bg,
            "A hold unwarranted in every company should still be released.",
        )
