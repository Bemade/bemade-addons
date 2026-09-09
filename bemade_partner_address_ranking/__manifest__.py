# Copyright (C) 2024 Bemade Inc. (<https://www.bemade.org>).
# License LGPL-3 or later (http://www.gnu.org/licenses/lgpl).
{
    "name": "Partner Address Ranking",
    "version": "18.0.1.3.0",
    "category": "Sales/CRM",
    "summary": (
        "Ranks company child addresses by usage on sales orders and allows"
        " explicit favorite invoice/delivery address overrides."
    ),
    "description": """
Partner Address Ranking
=======================

This module extends ``res.partner`` and ``sale.order`` to surface the most
relevant invoice and delivery addresses for a company when creating a new sales
order.

Features
--------

* **Favorite flags** — any child contact of a company can be marked as the
  default invoice or delivery address via two new checkboxes on the partner
  form.  Only one contact per company per address type may hold the flag
  (enforced by a Python constraint).
* **Usage-based ranking** — when no favorite is set the module picks the
  address most often used on confirmed / done sales orders for that company.
* **Picker ordering** — the address Many2one dropdowns on sales orders show
  favorite and high-usage addresses at the top of the list.
* **Full fallback** — if no history and no favorite exists the module falls
  back transparently to Odoo's stock ``address_get`` logic.
* **Non-destructive** — uninstalling the module reverts all behavior; no
  stored counters are added to partner records.
    """,
    "author": "Bemade Inc.",
    "website": "https://www.bemade.org",
    "license": "LGPL-3",
    "depends": ["sale", "contacts"],
    "data": [
        "views/res_partner_views.xml",
    ],
    "assets": {
        "web.assets_tests": [
            "bemade_partner_address_ranking/static/tests/tours/**/*",
        ],
    },
    "installable": True,
    "auto_install": False,
}
