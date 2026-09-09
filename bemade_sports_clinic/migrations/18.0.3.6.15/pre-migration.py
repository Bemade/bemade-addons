"""Scrub stray HTML markup from text-typed note fields.

Background
----------
sports.patient.injury.internal_notes / .external_notes,
sports.patient.team_info_notes / .allergies were modeled as fields.Html
in early iterations and are now fields.Text. Existing rows on installs
that went through the Html era retain the markup (<p>...</p>, <br/>,
&nbsp;, etc.), and since the fields are now plain text the markup is
shown literally — visible to portal users and during chatter logging.

This pre-migration walks each affected column and rewrites any value
that looks HTML-ish to plain text by:

1. Stripping HTML tags via Python's HTMLParser.
2. Decoding common HTML entities (&nbsp;, &amp;, &lt;, &gt;, &quot;,
   &#39;).
3. Collapsing the result and trimming surrounding whitespace.

Idempotent: rows that don't contain '<' or '&' are left untouched.
"""

import html
import logging
from html.parser import HTMLParser

_logger = logging.getLogger(__name__)


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._chunks = []

    def handle_data(self, data):
        self._chunks.append(data)

    def handle_starttag(self, tag, attrs):
        if tag in ('p', 'br', 'div', 'li', 'tr'):
            self._chunks.append('\n')

    def handle_endtag(self, tag):
        if tag in ('p', 'div', 'li', 'tr'):
            self._chunks.append('\n')

    def get_text(self):
        return ''.join(self._chunks)


def _strip(value):
    if not value:
        return value
    if '<' not in value and '&' not in value:
        return value
    parser = _TextExtractor()
    try:
        parser.feed(value)
        parser.close()
    except Exception:
        # On malformed HTML, fall back to a best-effort entity decode.
        return html.unescape(value).strip()
    text = html.unescape(parser.get_text())
    # Collapse consecutive blank lines and trim ends.
    lines = [line.rstrip() for line in text.splitlines()]
    out = []
    blank = False
    for line in lines:
        if not line.strip():
            if not blank and out:
                out.append('')
            blank = True
        else:
            out.append(line)
            blank = False
    return '\n'.join(out).strip()


TARGETS = (
    ('sports_patient_injury', 'internal_notes'),
    ('sports_patient_injury', 'external_notes'),
    ('sports_patient', 'team_info_notes'),
    ('sports_patient', 'allergies'),
)


def migrate(cr, version):
    for table, column in TARGETS:
        cr.execute(
            f"""
            SELECT id, {column}
            FROM {table}
            WHERE {column} IS NOT NULL
              AND ({column} LIKE '%<%' OR {column} LIKE '%&%')
            """
        )
        rows = cr.fetchall()
        if not rows:
            continue
        updated = 0
        for row_id, raw in rows:
            cleaned = _strip(raw)
            if cleaned != raw:
                cr.execute(
                    f"UPDATE {table} SET {column} = %s WHERE id = %s",
                    (cleaned, row_id),
                )
                updated += 1
        _logger.info(
            "Scrubbed HTML residue from %s.%s on %d rows.",
            table, column, updated,
        )
