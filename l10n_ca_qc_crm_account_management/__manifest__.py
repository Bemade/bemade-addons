{
    "name": "Quebec Localization: CRM Account Management Regions",
    "version": "18.0.1.0.0",
    "category": "Localization",
    "summary": "Derive the Quebec administrative region for customer accounts",
    "description": """
Quebec Localization: CRM Account Management Regions
===================================================

Quebec-specific overlay for ``crm_account_management``. Keeps the
province-agnostic base module free of Quebec administrative logic.

Adds to the customer account (``organizational.unit``):

- A stored, computed **QC Administrative Region** Selection field (one of the
  17 official Quebec administrative regions), derived from the owning
  partner's postal-code FSA (forward sortation area).
- Group-by / filter on the QC administrative region in the account search
  view, and the region column on the list view.

The derivation logic lives in a pure, unit-testable helper
(``models/qc_regions.py``); the FSA → region map is a curated subset and
best-effort for unmapped FSAs.
    """,
    "author": "Bemade Inc.",
    "website": "https://www.bemade.org",
    "license": "LGPL-3",
    "depends": [
        "crm_account_management",
    ],
    "data": [
        "views/organizational_unit_views.xml",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
}
