import logging

_logger = logging.getLogger(__name__)

# ``provider`` was a free Char; normalize pre-existing rows to the Selection
# keys ``conversation_imap``/``conversation_gmail`` register via
# ``selection_add`` (task #3965). Known free-text variants seen prior to this
# migration are mapped to their canonical key; anything unrecognized is
# cleared rather than left as a value the new Selection field cannot display.
_ALIASES = {
    "gmail": "gmail",
    "google": "gmail",
    "google mail": "gmail",
    "imap": "imap",
    "smtp": "imap",
    "email": "imap",
    "generic imap": "imap",
}


def migrate(cr, version):
    """Char -> Selection is storage-compatible (both varchar column types),
    so no schema change is needed -- only a value cleanup. Runs
    pre-migrate, before the upgraded Selection field is live, so no stray
    free-text value is ever exposed as an invalid/undisplayable option.
    Idempotent: safe to re-run.
    """
    cr.execute(
        "SELECT id, provider FROM conversation_transport WHERE provider IS NOT NULL"
    )
    rows = cr.fetchall()
    if not rows:
        return

    updates = []
    for row_id, raw in rows:
        normalized = _ALIASES.get((raw or "").strip().lower())
        if normalized != raw:
            updates.append((normalized, row_id))

    if not updates:
        return

    cr.executemany(
        "UPDATE conversation_transport SET provider = %s WHERE id = %s", updates
    )
    _logger.info(
        "conversation_transport: normalized %d provider value(s) for the "
        "Char -> Selection migration.",
        len(updates),
    )
