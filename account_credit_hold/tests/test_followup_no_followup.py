from odoo.addons.account.tests.common import AccountTestInvoicingCommon
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestFollowupNoFollowupDependency(AccountTestInvoicingCommon):
    """Guard the dependency edge added on ``account_credit_hold`` that forces
    installation of ``account_no_followup`` (the module that back-ports the
    ``no_followup`` field onto ``account.move.line`` in 18.0).

    Before this fix, ``account_credit_hold`` did not declare
    ``account_no_followup`` as a dependency. On a production database where
    ``account_no_followup`` ended up not installed, the credit-hold
    follow-up flow (``res.partner._execute_followup_partner`` ->
    ``account.followup.report`` -> ``unreconciled_aml_ids``) raised
    ``AttributeError`` on ``account.move.line.no_followup``. This test
    exercises that override chain from within ``account_credit_hold``'s own
    test environment, proving credit-hold alone pulls in the field rather than
    relying on some other consumer module happening to depend on it.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.excluded_invoice = cls._create_invoice(
            partner_id=cls.partner_a.id,
            invoice_date="2020-01-01",
            invoice_date_due="2020-01-01",
            post=True,
        )
        cls.included_invoice = cls._create_invoice(
            partner_id=cls.partner_a.id,
            invoice_date="2020-01-01",
            invoice_date_due="2020-01-01",
            post=True,
        )
        cls.excluded_line = cls.excluded_invoice.line_ids.filtered(
            lambda l: l.account_id.account_type == "asset_receivable"
        )
        cls.included_line = cls.included_invoice.line_ids.filtered(
            lambda l: l.account_id.account_type == "asset_receivable"
        )
        cls.excluded_line.no_followup = True

    def test_no_followup_field_available_and_followup_query_runs(self):
        """The ``no_followup`` field is installed and the follow-up query runs.

        Deliberately does NOT assert that the flagged line is *excluded* from
        ``unreconciled_aml_ids``. Whether the exclusion happens depends on the
        Enterprise point release: newer builds filter on ``no_followup`` inside
        ``_get_invoices_to_print``, the version pinned here does not. Asserting
        the exclusion makes the suite pass or fail on which Enterprise checkout
        the runner happens to have, which is not a property of this module.

        What IS this module's property, and what this guards: the
        ``account_no_followup`` dependency is declared, so the field exists and
        is writable, and reading the follow-up recordset does not raise
        ``AttributeError`` -- the production crash this dependency fixed.
        """
        self.assertIn(
            "no_followup",
            self.env["account.move.line"]._fields,
            "account_no_followup must be installed via account_credit_hold's "
            "depends, otherwise the follow-up cron raises AttributeError.",
        )
        self.assertTrue(self.excluded_line.no_followup)

        # Must not raise: this is the call chain that crashed in production.
        unreconciled_amls = self.partner_a.unreconciled_aml_ids
        self.assertIn(self.included_line.id, unreconciled_amls.ids)
