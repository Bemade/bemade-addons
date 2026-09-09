# -*- coding: utf-8 -*-
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).
# Copyright (C) 2026 Bemade Inc., Marc Durepos <marc@bemade.org>
from odoo import fields, models

# Explicit accent → ASCII map. Kept inline (no unicodedata import) so the
# helper is callable from ir.actions.report's safe_eval context without
# having to whitelist new globals.
_ACCENT_MAP = str.maketrans({
    "à": "a", "â": "a", "ä": "a", "á": "a", "ã": "a", "å": "a",
    "ç": "c",
    "è": "e", "é": "e", "ê": "e", "ë": "e",
    "ì": "i", "î": "i", "ï": "i", "í": "i",
    "ñ": "n",
    "ò": "o", "ô": "o", "ö": "o", "ó": "o", "õ": "o",
    "ù": "u", "û": "u", "ü": "u", "ú": "u",
    "ý": "y", "ÿ": "y",
    "À": "A", "Â": "A", "Ä": "A", "Á": "A", "Ã": "A", "Å": "A",
    "Ç": "C",
    "È": "E", "É": "E", "Ê": "E", "Ë": "E",
    "Ì": "I", "Î": "I", "Ï": "I", "Í": "I",
    "Ñ": "N",
    "Ò": "O", "Ô": "O", "Ö": "O", "Ó": "O", "Õ": "O",
    "Ù": "U", "Û": "U", "Ü": "U", "Ú": "U",
    "Ý": "Y", "Ÿ": "Y",
    "Œ": "OE", "œ": "oe", "Æ": "AE", "æ": "ae",
    "ß": "ss",
})


class ResPartner(models.Model):
    _inherit = "res.partner"

    def _account_statement_filename(self):
        """Return a safe, meaningful filename (no extension) for this
        partner's customer account statement PDF.

        Format: ``Customer_Account_Statement_<Partner>_<YYYY-MM-DD>``

        - ``<Partner>`` is ``commercial_company_name or name`` with accents
          stripped and any run of non-``[A-Za-z0-9-]`` characters collapsed
          to a single ``_``. Falls back to ``client`` if the partner has no
          usable name at all.
        - ``<YYYY-MM-DD>`` is today's date in the user's timezone, via
          ``fields.Date.context_today``.

        Odoo appends ``.pdf`` automatically when rendering the report.
        """
        self.ensure_one()
        raw = self.commercial_company_name or self.name or "client"
        ascii_name = raw.translate(_ACCENT_MAP)
        cleaned, prev_us = [], False
        for ch in ascii_name:
            if ch.isalnum() or ch == "-":
                cleaned.append(ch)
                prev_us = False
            elif not prev_us:
                cleaned.append("_")
                prev_us = True
        slug = "".join(cleaned).strip("_") or "client"
        date_str = fields.Date.context_today(self).strftime("%Y-%m-%d")
        return f"Customer_Account_Statement_{slug}_{date_str}"
