# Copyright 2026 Bemade Inc.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).
{
    "name": "Mail Author Visibility",
    "version": "18.0.1.0.0",
    "category": "Discuss",
    "summary": (
        "Injects a 'Posted by:' author header block into chatter notification "
        "emails so recipients immediately know who posted each message."
    ),
    "description": """
Mail Author Visibility
======================

When followers receive chatter notification emails, the sender's identity is
not always obvious — particularly when messages lack a manual signature or
come from unfamiliar contacts.

This module extends the two stock Odoo 18 notification layout templates
(``mail.mail_notification_layout`` and ``mail.mail_notification_light``) via
``xpath`` inheritance to prepend a translatable **"Posted by:"** block just
above the message body.  The block shows:

- **Name** — taken from ``message.author_id.name`` when an internal partner is
  linked; falls back to the raw ``message.email_from`` string for inbound
  emails that could not be matched to a partner.
- **Email** — ``message.author_id.email`` rendered as a ``mailto:`` link when
  available.

The block is wrapped in ``t-if="author_display_name or author_display_email"``
so it is completely suppressed on system-generated messages that carry no
author information.

No new models or fields are introduced.  The module is safe to install or
uninstall at any time; templates revert to stock Odoo on the next module
upgrade after uninstall.

Ships with a Quebec French translation (``fr_CA``) out of the box.
    """,
    "author": "Bemade Inc.",
    "maintainers": ["mdurepos"],
    "website": "https://www.bemade.org",
    "depends": ["mail"],
    "data": [
        "views/mail_notification_layout.xml",
    ],
    "auto_install": ["mail"],
    "installable": True,
    "license": "LGPL-3",
}
