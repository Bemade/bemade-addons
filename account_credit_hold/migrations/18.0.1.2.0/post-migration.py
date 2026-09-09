"""Re-align hold_bg with reality after it stopped being a computed field.

Until 18.0.1.2.0 the hold was released as a side effect of reading the
non-stored ``followup_status``, so whether a partner's flag matched the
follow-up rule depended on whether anyone had happened to open their record.
Now that the flag is explicit state it will persist, which means whatever it
says at upgrade time is what sticks.

Release-only on purpose: this clears holds the rule no longer warrants, and
never places one. Placing stays with the follow-up run, which emails the
customer -- an upgrade must not silently start blocking sales orders.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    from odoo import SUPERUSER_ID, api

    env = api.Environment(cr, SUPERUSER_ID, {})
    Partner = env["res.partner"]

    held = Partner.search([("hold_bg", "=", True)])
    if not held:
        _logger.info("account_credit_hold: no partner on hold, nothing to re-align")
        return

    # Evaluate per company: the follow-up query is scoped by allowed_company_ids.
    released = Partner.browse()
    for company in env["res.company"].search([]):
        in_company = held.filtered(
            lambda p, c=company: not p.company_id or p.company_id == c
        )
        if in_company:
            released |= in_company.with_company(company)._evaluate_credit_hold_release()

    _logger.info(
        "account_credit_hold: re-aligned %s partner(s) on hold, released %s",
        len(held),
        len(released),
    )
