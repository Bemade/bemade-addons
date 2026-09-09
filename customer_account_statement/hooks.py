# -*- coding: utf-8 -*-
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).
# Copyright (C) 2026 Bemade Inc., Marc Durepos <marc@bemade.org>
import logging

_logger = logging.getLogger(__name__)

_PRINT_REPORT_NAME = "object._account_statement_filename()"
_REPORT_XMLID = (
    "customer_account_statement.action_report_customer_account_statement"
)


def _set_print_report_name(env):
    """Set print_report_name on the customer account statement report if empty.

    Safe to call on both fresh install and upgrade. Preserves any value an
    admin has already set.
    """
    report = env.ref(_REPORT_XMLID, raise_if_not_found=False)
    if not report:
        _logger.warning(
            "Customer account statement report record missing; "
            "skipping print_report_name setup."
        )
        return
    if report.print_report_name:
        _logger.info(
            "print_report_name already set to %r; "
            "preserving admin override (no-op).",
            report.print_report_name,
        )
        return
    report.print_report_name = _PRINT_REPORT_NAME
    _logger.info(
        "Set print_report_name to helper expression on "
        "customer_account_statement report."
    )


def post_init_hook(env):
    """Called after fresh install. Sets print_report_name if empty."""
    _set_print_report_name(env)
