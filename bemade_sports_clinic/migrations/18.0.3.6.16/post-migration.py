"""Reconcile stale mail.activity assignments on existing data.

The 18.0.3.6.16 release tightens the portal mail.activity rule to drop the
"(user_id == self) AND res_model in [...]" OR-branch. Activities still
assigned to a user who is no longer on staff for any of the related
patient's teams would otherwise become silently invisible in the portal.

This post-migration runs the new cleanup helper across every active
sports.patient.injury so existing stale assignments are reassigned (or
unlinked when there's no current team therapist to take them over).
"""
import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    injuries = env['sports.patient.injury'].sudo().search([])
    if not injuries:
        return
    _logger.info(
        "[bemade_sports_clinic 18.0.3.6.16] reconciling mail.activity "
        "assignments across %d injuries",
        len(injuries),
    )
    injuries._cleanup_stale_mail_activities()
