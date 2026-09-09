import logging
from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """One-time: set print_report_name on the customer account statement
    report only if it is currently empty. Preserves any admin hand-edits.

    Runs on upgrade (state == 'to upgrade'). Fresh installs are handled by
    the post_init_hook in hooks.py because Odoo 18 skips migrations when
    the module state is 'to install'.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    report = env.ref(
        "customer_account_statement.action_report_customer_account_statement",
        raise_if_not_found=False,
    )
    if not report:
        _logger.warning(
            "Customer account statement report record missing; "
            "skipping print_report_name migration."
        )
        return
    if report.print_report_name:
        _logger.info(
            "print_report_name already set to %r; "
            "preserving admin override (no-op).",
            report.print_report_name,
        )
        return
    report.print_report_name = "object._account_statement_filename()"
    _logger.info(
        "Set print_report_name to helper expression on "
        "customer_account_statement report."
    )
