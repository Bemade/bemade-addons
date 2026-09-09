# Copyright (C) 2026 Bemade Inc.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Bemade Mail Gateway Endpoint",
    "version": "18.0.1.0.1",
    "category": "Tools",
    "summary": (
        "Token-authenticated HTTP endpoint to push raw mail into Odoo "
        "without consuming a user license."
    ),
    "description": """
Bemade Mail Gateway Endpoint
============================

Exposes ``POST /bemade/mail-gateway/process`` so that external mail
relays — first and foremost the ``odoo-mail-gateway`` LMTP sidecar —
can push raw RFC 5322 messages into ``mail.thread.message_process``
authenticated by a shared secret token instead of by a per-user API
key.

Why
---
The standard ``/jsonrpc`` route requires an active ``Internal User``,
which is a billable seat in Odoo Enterprise (~30 $ CAD/month/user).
This module replaces that auth with a hashed, rotatable token managed
under Settings → Bemade → Mail Gateway Tokens — no licensed user
needed.

See ``docs/`` for the full design specification.
    """,
    "author": "Bemade Inc.",
    "website": "https://git.bemade.org/bemade/bemade_mail_gateway",
    "license": "AGPL-3",
    "depends": [
        "base",
        "mail",
    ],
    "data": [
        "security/security.xml",
        "security/ir.model.access.csv",
        "views/wizard_views.xml",
        "views/token_views.xml",
        "views/menus.xml",
    ],
    "external_dependencies": {"python": []},
    "installable": True,
    "application": False,
    "auto_install": False,
}
