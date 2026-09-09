# License: LGPL-3
# Author: Bemade Inc. (Marc Durepos <marc@bemade.org>)
"""Post-migration: backfill line_source='invoice' on existing rows.

Odoo normally backfills the default value for a new required Selection field
on upgrade, but this explicit UPDATE guarantees correctness even if the ORM
skips the backfill (e.g. when the column already exists with NULLs from a
partial upgrade).
"""


def migrate(cr, version):
    cr.execute(
        """
        UPDATE commercial_invoice
        SET line_source = 'invoice'
        WHERE line_source IS NULL
        """
    )
