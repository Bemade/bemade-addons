# Acceptance criteria (task #3965, conversation_base.tools.mime):
#   Blocking issue #2 -- pure-function coverage of the shared RFC822/MIME
#   helpers conversation_imap/conversation_gmail's _normalize both call
#   (never duplicated per provider): HTML sanitization runs even on a
#   non-multipart text/html message, extract_attachments never raises on
#   a non-multipart message, and correlation_candidates dedupes
#   In-Reply-To/References. The higher-value end-to-end coverage (real
#   .eml fixtures through _normalize -- multipart/alternative,
#   multipart/mixed with attachments, quoted-printable, non-UTF-8
#   charset) lives in conversation_imap's tests, since that's where the
#   fixtures + the transport that calls _normalize both live.

import email
import email.policy

from odoo.tests import TransactionCase

from odoo.addons.conversation_base.tools import mime


def _parse(raw_text):
    return email.message_from_string(raw_text, policy=email.policy.default)


class TestMimeExtractBody(TransactionCase):
    def test_sanitizes_non_multipart_html(self):
        message = _parse(
            "Content-Type: text/html; charset=UTF-8\n\n"
            "<p>Hi</p><script>alert(1)</script>"
        )
        body = mime.extract_body(message)
        self.assertIn("<p>Hi</p>", body)
        self.assertNotIn("<script", body)

    def test_never_raises_on_unparseable_content(self):
        class _BrokenMessage:
            def is_multipart(self):
                raise RuntimeError("boom")

        self.assertEqual(mime.extract_body(_BrokenMessage()), "")


class TestMimeExtractAttachments(TransactionCase):
    def test_non_multipart_has_no_attachments(self):
        message = _parse("Content-Type: text/plain; charset=UTF-8\n\nHello")
        self.assertEqual(mime.extract_attachments(message), [])


class TestMimeCorrelationCandidates(TransactionCase):
    def test_dedupes_in_reply_to_and_references(self):
        message = _parse(
            "In-Reply-To: <a@example.com>\n"
            "References: <root@example.com> <a@example.com>\n"
            "Content-Type: text/plain\n\nbody"
        )
        candidates = mime.correlation_candidates(message)
        self.assertEqual(candidates, {"<a@example.com>", "<root@example.com>"})

    def test_no_headers_returns_empty_set(self):
        message = _parse("Content-Type: text/plain\n\nbody")
        self.assertEqual(mime.correlation_candidates(message), set())
