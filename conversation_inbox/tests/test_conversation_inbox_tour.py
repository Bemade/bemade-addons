# Acceptance criteria (task #3965, AC5/AC6 -- the viewer itself):
#   - The inbox client action mounts, lists a browse page, pages
#     forward/back, expands an item, and opens each triage dialog.
#   - The composer opens prefilled (subject, recipient, quoted original)
#     with the attachments control reachable without scrolling past the
#     draft.
#
# Why this exists as a TOUR and not more TransactionCase tests: the two
# defects that shipped this feature broken were both invisible to Python.
# The triage buttons were dead because an inline doAction dict used
# `view_mode` where the client action schema wants `views` -- server-side
# nothing is wrong, the wizards work when called directly, and every
# wizard test passed. Only a browser clicking the real button sees it.

from unittest.mock import patch

from odoo.tests import HttpCase, tagged

_TOUR_ITEMS = {
    "1": {
        "subject": "Tour Message A",
        "email_from": "tourist@example.com",
        "date": "2026-08-14 09:00:00",
    },
    "2": {
        "subject": "Tour Message B",
        "email_from": "other@example.com",
        "date": "2026-08-14 08:00:00",
    },
    "3": {
        "subject": "Tour Message C",
        "email_from": "third@example.com",
        "date": "2026-08-13 17:00:00",
    },
}


def _stub(external_id):
    """One canonical `_normalize` dict, as the engine would return it."""
    item = _TOUR_ITEMS[external_id]
    return {
        "external_id": external_id,
        "message_id": "<tour-%s@example.com>" % external_id,
        "subject": item["subject"],
        "email_from": item["email_from"],
        "author": item["email_from"],
        "to": ["desk@example.com"],
        "cc": ["watcher@example.com"],
        "date": item["date"],
        "body": "<p>Here is the quote you asked for.</p>",
        "attachments": [{"filename": "quote.pdf", "mimetype": "application/pdf"}],
    }


def _fake_browse(self, query=None, page=1):
    """Page 1 = A + B with more to come, page 2 = C. Enough for the tour
    to page forward and back over a stable, socket-free mailbox."""
    if (page or 1) <= 1:
        return {
            "items": [_stub("1"), _stub("2")],
            "page": 1,
            "page_size": 2,
            "has_more": True,
        }
    return {"items": [_stub("3")], "page": 2, "page_size": 2, "has_more": False}


def _fake_fetch(self, external_id):
    return {"external_id": external_id, "rfc822": b""}


def _fake_normalize(self, raw):
    return _stub(raw["external_id"])


@tagged("post_install", "-at_install")
class TestConversationInboxTour(HttpCase):
    def test_inbox_tour(self):
        transport_model = self.env["conversation.transport"]
        # user_id False = a shared transport, so it is visible to whoever
        # the tour logs in as under conversation_base's own-or-shared rule.
        transport_model.create(
            {
                "name": "Tour Mailbox",
                "login": "desk@example.com",
                "browsable": True,
                "sendable": True,
                "user_id": False,
            }
        )
        # The tour drives the real client action over HTTP, but the
        # transport must never open a socket -- so the three engine hooks
        # the viewer and the composer read through are stubbed on the
        # registry class, which the request threads share.
        cls = type(transport_model)
        with patch.object(cls, "_browse", _fake_browse), patch.object(
            cls, "_fetch", _fake_fetch
        ), patch.object(cls, "_normalize", _fake_normalize):
            self.start_tour(
                "/odoo/action-conversation_inbox.conversation_inbox_client_action",
                "conversation_inbox_tour",
                login="admin",
            )
