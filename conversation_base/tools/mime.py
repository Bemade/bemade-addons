"""Pure RFC822/MIME parsing helpers shared by IMAP-speaking transport
providers (``conversation_imap``, ``conversation_gmail`` -- Gmail's
browse/fetch also happen over IMAP, just with XOAUTH2 auth instead of a
password). Plain functions, no ORM/model dependency, so both provider
modules can import them without depending on each other -- only on
``conversation_base``, which they already do.
"""

from email.utils import getaddresses, parsedate_to_datetime

from odoo.tools.mail import html_sanitize, plaintext2html


def addresses(header_value):
    """A ``To``/``Cc`` header value -> list of bare email addresses."""
    return [addr for _name, addr in getaddresses([header_value or ""]) if addr]


def first_address(header_value):
    """A ``From`` header value -> its single bare email address, or ''."""
    found = addresses(header_value)
    return found[0] if found else ""


def parse_date(date_header):
    """An RFC822 ``Date`` header -> an aware ``datetime``, or ``False``."""
    if not date_header:
        return False
    try:
        return parsedate_to_datetime(date_header)
    except (TypeError, ValueError):
        return False


def extract_body(message):
    """Prefer the HTML part of a parsed ``email.message.Message`` (walking
    ``multipart/alternative``/``multipart/mixed`` via the stdlib's own
    ``get_body()``, which skips attachments), fall back to plaintext --
    escaped and converted via ``odoo.tools.plaintext2html`` (never
    raw-interpolated into HTML, to avoid a plaintext body's own angle
    brackets being rendered as markup). Every HTML body -- whether the
    email's own ``text/html`` part or plaintext promoted to HTML -- is run
    through Odoo's own ``html_sanitize`` before it ever reaches the inbox
    viewer, the same tooling ``mail.message`` bodies go through elsewhere
    in Odoo; a raw inbound email is untrusted input. Never raises on an
    unusual MIME layout -- a part that can't be decoded degrades to an
    empty body rather than a 500."""
    try:
        if message.is_multipart():
            html_part = message.get_body(preferencelist=("html",))
            if html_part is not None:
                return html_sanitize(html_part.get_content())
            text_part = message.get_body(preferencelist=("plain",))
            if text_part is not None:
                return html_sanitize(plaintext2html(text_part.get_content()))
            return ""
        content_type = message.get_content_type()
        content = message.get_content()
        if content_type == "text/html":
            return html_sanitize(content)
        return html_sanitize(plaintext2html(content))
    except Exception:  # noqa: BLE001 - never raise on an unusual MIME layout
        return ""


def extract_attachments(message):
    """List the non-body parts of a parsed ``email.message.Message`` as
    lightweight metadata (filename/content type/size) -- never the encoded
    payload itself. The inbox viewer lists attachments rather than
    inlining them (task #3965): a human decides whether to pull one into
    Odoo as part of a GTD capture action, not have it silently embedded.
    Never raises on an unusual MIME layout."""
    if not message.is_multipart():
        return []
    attachments = []
    try:
        parts = list(message.iter_attachments())
    except Exception:  # noqa: BLE001 - never raise on an unusual MIME layout
        return []
    for part in parts:
        try:
            payload = part.get_payload(decode=True) or b""
            size = len(payload)
        except Exception:  # noqa: BLE001 - a single bad part shouldn't
            # hide every other attachment
            size = 0
        attachments.append(
            {
                "filename": part.get_filename() or "attachment",
                "content_type": part.get_content_type(),
                "size": size,
            }
        )
    return attachments


def extract_attachment_payloads(message):
    """Like ``extract_attachments``, but with the decoded bytes -- for
    re-attaching an original's files to a forward. Kept separate rather
    than a flag on ``extract_attachments`` because the two have opposite
    costs: listing metadata for an inbox page must stay cheap, while this
    materializes every payload in memory and is only ever wanted for the
    one message a human chose to forward. Never raises on an unusual MIME
    layout; a part that cannot be decoded is skipped rather than
    replaced with a corrupt attachment."""
    if not message.is_multipart():
        return []
    payloads = []
    try:
        parts = list(message.iter_attachments())
    except Exception:  # noqa: BLE001 - never raise on an unusual MIME layout
        return []
    for part in parts:
        try:
            content = part.get_payload(decode=True)
        except Exception:  # noqa: BLE001 - a single bad part shouldn't
            # cost the reader every other attachment
            continue
        if not content:
            continue
        payloads.append(
            {
                "filename": part.get_filename() or "attachment",
                "content": content,
                "mimetype": part.get_content_type(),
            }
        )
    return payloads


def correlation_candidates(message):
    """A parsed message's In-Reply-To + References headers -> the set of
    message-ids a within-transport ``_match_inbound`` should search
    ``mail.message.message_id`` for. Not ``external_id``: on an email
    transport that holds the IMAP UID, not an RFC id."""
    candidates = set()
    in_reply_to = (message.get("In-Reply-To") or "").strip()
    if in_reply_to:
        candidates.add(in_reply_to)
    references = (message.get("References") or "").split()
    candidates.update(ref.strip() for ref in references if ref.strip())
    return candidates
