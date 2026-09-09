import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Mirror every pre-existing v1 native link (``documents.document``'s
    single ``res_model``/``res_id`` pointer) into a ``bemade.documents.link``
    row, so linked-record counts/filters built on the new model include data
    that predates it (task #3678). Runs post-migrate so the new model's table
    already exists. Idempotent: safe to re-run on upgrade re-runs.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    documents = env["documents.document"].search(
        [
            ("res_model", "!=", "documents.document"),
            ("res_model", "!=", False),
            ("res_id", "!=", False),
        ]
    )
    if not documents:
        _logger.info("No pre-existing native document links to mirror; skipping.")
        return

    Link = env["bemade.documents.link"]
    existing = Link.search([("document_id", "in", documents.ids)])
    already_mirrored = {
        (link.document_id.id, link.res_model, link.res_id) for link in existing
    }

    vals_list = [
        {
            "document_id": document.id,
            "res_model": document.res_model,
            "res_id": document.res_id,
        }
        for document in documents
        if (document.id, document.res_model, document.res_id) not in already_mirrored
    ]
    if not vals_list:
        _logger.info("All native document links already mirrored; skipping.")
        return

    Link.with_context(skip_bemade_link_audit=True).create(vals_list)
    _logger.info("Mirrored %d native document link(s) into bemade.documents.link.", len(vals_list))
