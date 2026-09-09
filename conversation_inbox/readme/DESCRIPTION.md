In-Odoo GTD inbox/triage viewer for `browsable` conversation transports
(task #3965, epic 03). Explicitly **not** a replacement email client: an
ingest-on-action funnel that captures any inbox item into the Conversations
hub (`conversation_base`) without persisting anything until a human files
it.

## What this ships

- An OWL client action (`Inbox`, in the Conversations app menu) that lists
  message stubs a page at a time from the user's `browsable` transport(s),
  fetching a message's full envelope only when expanded -- nothing is
  written to Odoo just by looking.
- The full GTD action set from an inbox item: file as a **new
  conversation**, **add to an existing conversation**, **link to a
  record**, **reassign** to a colleague/team, **reply / reply-all /
  forward** (composer only offered on `sendable` transports), **route
  through an alias** (feeds the raw envelope into the ordinary mail
  gateway), and **dismiss** (archives an already-filed conversation; a
  pure client-side no-op if the item was never filed -- there is nothing
  to delete server-side when nothing was ever persisted).
- Three dialog wizards (`conversation.inbox.capture.wizard`,
  `conversation.inbox.reassign.wizard`, `conversation.inbox.reply.wizard`)
  carrying the actual filing logic, all built on
  `mail.conversation._capture_or_find` -- so acting twice on the same
  inbox item (e.g. replying, then later reassigning) never files a
  duplicate conversation.
- The per-user **"My Mail Accounts"** menu (task AC4): the generic
  `conversation.transport` form/list/search views `conversation_base`
  ships, opened with a "mine first" default context; the underlying
  own+shared `ir.rule` (already in `conversation_base`) is what actually
  scopes visibility.
- An expanded message renders like a mail client, not raw MIME source: the
  sanitized HTML body from the transport's `_normalize` (`conversation_base.
  tools.mime`) via `t-out`, plus a separate list of attachment chips
  (filename only -- never the encoded payload inlined into the body; a
  human decides whether to pull one into Odoo as part of a GTD capture
  action).
- A failed action (e.g. browsing an account that isn't fully configured)
  shows that failure's **own** message as the notification, not a generic
  "Odoo Server Error" toast -- Odoo's JSON-RPC envelope carries the actual
  exception text under `error.data.message`, not the top-level
  `error.message`, which every catch block here now reads from.

## Deliberately out of scope here (see task's Deviations)

- `conversation_inbox_forward` (a thin bridge reusing epic 08's
  `mail.message._do_forward()`/`mail.forward.wizard`) was **not built** in
  this pass: that Forward feature isn't reachable from this branch's base
  (it lives only on `origin/18.0`, two commits ahead of what
  `conversation_base` is pinned to here). Per the task design's own
  documented fallback, inbox-item Forward instead uses
  `mail.conversation.action_forward()` (this module's own
  `transport._send`-based primitive) directly.

## The composer (18.0.2.0.0)

Reply / reply-all / forward open a transient composer that is deliberately
**not** a `mail.compose.message`. That model exists to persist — it creates
`mail.mail` and `mail.message` records and sends through `ir.mail_server` —
and the default path here must do none of those things. The widgets are
reused; the model is not.

- **Filing is optional and off by default.** `file_in_odoo` unchecked means
  the message is sent through the account's own transport and *nothing* is
  recorded in Odoo: no conversation, no `mail.message`, no link. Triage from
  someone's personal mailbox should not deposit message bodies in the shared
  hub unless they say so, per message. A shared or team mailbox can flip the
  default per account with `default_file_in_odoo` on the transport.
- **When filing is on**, the *original* inbox item is captured (into a new
  conversation or one you pick) and the outgoing message is recorded beside
  it, so the conversation reads as the exchange rather than half of it.
  Idempotent: acting twice on the same item never files a second
  conversation.
- **To / Cc / Bcc are free text**, comma-separated, prefilled from the
  original envelope — reply goes to the sender, reply-all adds everyone else
  who was on it minus this account. Correspondents are very often not
  partners, and a forward explicitly accepts any address; partner matching
  happens after the send and only when filing. Bcc goes in the SMTP envelope
  only, and is never recorded when filing — that is the one thing a Bcc
  promises.
- **Signature and the quoted original are prefilled into the editable
  body**, never appended at send time, so you can trim either. One mechanism
  covers reply-quoting, forward-quoting and the signature.
- **Forward is a real forward**: the original is inline-quoted (what Gmail,
  Outlook and Apple Mail all default to, and what renders everywhere —
  unlike a `message/rfc822` attachment, which shows as an opaque blob on
  Gmail and Outlook mobile), its own attachments are re-attached, and the
  subject defaults to `Fwd: …`. The body is optional: passing an email along
  with no added comment is ordinary use. The re-attached files are read
  straight from the source mailbox at send time rather than copied into
  `ir.attachment` first, so forwarding stores nothing in Odoo either.
- If the mailbox is unreachable when the dialog opens, the composer opens
  empty rather than failing — prefilling is a convenience, not a
  precondition.

## Open design question — whose signature on a shared mailbox?

The composer prefills **the acting user's** signature (`env.user.signature`),
which is what Odoo does everywhere else and is plainly right for someone's
own mailbox.

For a *shared* mailbox it is a real question, not an oversight. A reply
leaving `support@` signed by whoever happened to pick the item up may be
exactly what a small team wants — correspondents like knowing who they are
talking to — or may be precisely what the shared address exists to avoid,
disclosing team structure and staffing to anyone who writes in.

Deliberately unresolved for this version, because the answer is a policy
choice per deployment rather than a technical one. Whoever picks it up:
the likely shape is a signature field on `conversation.transport` that
overrides the user's when set (blank = keep today's behaviour), which keeps
personal mailboxes untouched and makes the shared case explicit. Worth
settling before the hub is used by more than one team.
