The shared IMAP/SMTP engine behind every email `conversation.transport`
provider (task #3965). Not installed on its own: `conversation_imap`,
`conversation_gmail` (and any future `conversation_outlook`) depend on it
and supply only their connection layer.

## Why

Gmail's transport and a generic IMAP transport differ in exactly two ways:
which endpoints they talk to, and how they authenticate. Everything else --
paging a mailbox, fetching a message, parsing RFC822 into the canonical
stub, correlating a reply back to a thread, composing and delivering an
outbound message -- is the same IMAP/SMTP protocol work. That work lives
here, once.

Previously each provider module carried its own copy. Two copies drift:
`conversation_gmail`'s `_normalize` had silently stopped returning the
`attachments` key its `conversation_imap` twin returned, and every fix had
to be written twice.

## Provider-guarded dispatch, not module load order

Odoo has one way to extend a model: `_inherit`. So two provider modules
installed side by side both contribute overrides to the *same*
`conversation.transport` class, and whichever module Odoo loads last wins
the method -- silently, and by alphabetical accident. That is not a
theoretical hazard: it is how a Gmail transport came to be asked for a
generic `imap_host` field it has no reason to carry, failing with an error
naming `login` (which was set) rather than the field that was actually
empty.

Every provider override is therefore guarded on the record's own
`provider` value, the `payment.provider` pattern:

```python
def _email_connection_params(self):
    if self.provider != "gmail":
        return super()._email_connection_params()
    ...
```

The engine's own hooks do the same in the other direction: a transport
whose `provider` no installed email provider registered falls straight
through to `conversation_base`'s abstract hooks, so a future non-email
provider (SMS, WhatsApp, ...) is unaffected by this module being installed.

## What a provider module supplies

- `_email_providers()` -- append its `provider` code, so the engine knows
  the record is one of its own.
- `_email_connection_params()` -- `imap_host`, `imap_port`, `imap_ssl`,
  `smtp_host`, `smtp_port`, `smtp_starttls`, `password`. Guarded as above.
- `_imap_oauth_string(force_refresh=False)` -- optional. Return a SASL
  XOAUTH2 string to authenticate via OAuth instead of `login`/`password`,
  or leave the engine's `None` default for a password login. The engine
  owns the retry-once-with-a-refreshed-token path for both IMAP and SMTP,
  so a provider never reimplements it.

`login` is not part of the params: it lives on `conversation.transport`
itself and means the same thing for every provider.

## What the engine owns

- `_browse`/`_search_remote` -- paged message stubs (headers only:
  From/To/Cc/Subject/Date/Message-Id), newest first. A page is fetched by
  searching a *sequence-number window* (`SELECT` reports the message
  count; the newest page is the top of the range), never `UID SEARCH ALL`:
  that answers with every UID in the mailbox on one line, which imaplib
  refuses to read past 1 MB -- so the obvious implementation transfers
  megabytes to show 25 rows, and fails outright on a mailbox of a few
  hundred thousand messages. An explicit search query is the user's own
  narrowing and is issued as-is, with an ask-for-something-narrower error
  if it still overruns. A page costs **one `SELECT` and one `FETCH`**: the
  connection hands its EXISTS count to the pager rather than letting it
  re-`SELECT`, and the whole page's headers come back in a single UID set
  rather than one round trip per message (which measured 92s for 25 rows
  against a live Gmail account).
- The mailbox name is **quoted** in `SELECT`. imaplib passes it through
  verbatim, so an unquoted folder containing a space parses as two
  arguments -- which is every one of Gmail's special folders
  (`[Gmail]/Sent Mail`, `[Gmail]/All Mail`, ...).
- `_fetch`/`_normalize` -- download and parse a single message's full body
  only when a human expands it (ingest-on-action: nothing is persisted
  until then). MIME decoding goes through `conversation_base.tools.mime`:
  `text/html` preferred, `text/plain` promoted to HTML as a fallback, both
  run through Odoo's own `html_sanitize`; attachments listed as metadata,
  never inlined as encoded payloads.
- `_match_inbound` -- correlates a raw message's References/In-Reply-To
  against `mail.message.message_id`, **within this same transport only**.
  Not `external_id`: on an email transport that holds the IMAP UID, so
  comparing it to RFC message-ids never matched anything. Provenance is
  checked in Python rather than in the domain, because a quiet-captured
  inbound note leaves `transport_id` falsy on purpose (the
  notification-safety marker) and is identified by its conversation's
  `primary_transport_id` instead -- the same rule `_find_captured` and
  the reply-header lookup apply, shared as `_email_message_is_mine`.
- `_send` -- composes and delivers over SMTP as `multipart/alternative`
  (a `text/plain` part alongside the HTML), after rewriting root-relative
  links to absolute ones the way `mail_mail` does, so a link to an
  attachment or an inline image does not arrive dead. The outgoing
  Message-Id is the `mail.message`'s own, and a reply threads against the
  RFC822 Message-Id of the last message that actually travelled over this
  transport -- **not** its `external_id`, which on an IMAP capture is the
  per-mailbox UID and threads nowhere.
- Connection handling: `_imap_connection()`/`_smtp_connection()` are
  context managers that log in, yield, and always log out/close in a
  `finally` -- no socket is ever held between two separate requests. Every
  connection carries a socket timeout (`_email_socket_timeout()`, 30s):
  imaplib and smtplib default to none at all, so an unresponsive mail
  server would otherwise hold an Odoo worker until `limit_time_real`
  fires, and enough of those take the whole instance down -- health checks
  included, which turns a slow mailbox into a container restart. A
  small per-process LRU cache (`_ENVELOPE_CACHE`) avoids re-parsing the
  same message across nearby page views without needing a live connection.

## Testing note

This module has no provider of its own to connect with, so its IMAP/SMTP
behaviour is exercised end to end through the providers that do supply one
(`conversation_imap`'s and `conversation_gmail`'s suites) rather than
against a mocked-up connection layer here. Its own tests cover the one
thing only it can break: the non-email fall-through described above.
