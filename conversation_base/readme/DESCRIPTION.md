Introduces `mail.conversation` as a first-class triage unit, independent of
any single business record (sale order, ticket, invoice, ...).

## Why

Odoo's chatter ties a message thread to exactly one `res_model`/`res_id`.
Real-world email triage does not: a single conversation can be about several
records, and a single record can spawn several distinct conversations over
time. This module reifies the conversation itself as its own model, with:

- `mail.conversation` -- the conversation (state, assignee, team, tags,
  primary transport), inheriting the standard chatter (`mail.thread`),
  activities (`mail.activity.mixin`) and an inbound email alias
  (`mail.alias.mixin`).
- `mail.conversation.link` -- a reified generic link from a conversation to
  any number of business records (`res_model`/`res_id`), so a
  conversation<->record relationship is many-to-many instead of the native
  one-to-one chatter link.
- `mail.conversation.participant` -- who is on a conversation (partner or
  bare email address), distinct from `mail.followers`: adding a participant
  never subscribes anyone.
- `mail.conversation.member` -- per-user triage state (handled/unread/
  snoozed) on a conversation, independent of the conversation's own `state`.
- `mail.conversation.team` -- a dedicated team model for conversations,
  independent of CRM/Helpdesk/Discuss channel teams.
- `mail.conversation.tag` -- simple tags for conversations.
- `conversation.transport` -- a minimal stub comodel for the outbound/inbound
  channel (email, SMS, ...) a conversation or message travels over; later
  epics extend it with provider-specific behavior.
- `mail.message` is extended with `transport_id` and `external_id` so
  individual messages can be told apart from internal notes and correlated
  back to the native message id of the originating transport.

This module ships the skeleton only: no transports, no notify-safety
overrides, no triage UI beyond a basic list/form/kanban to exercise the
model. Those are delivered by later epics.

## Task #3965 -- transport interface + capture/gateway primitives

- `conversation.transport` gains the provider-agnostic interface (modeled on
  `payment.provider`): capability flags `browsable`/`searchable`/`pushable`/
  `sendable`/`artifact_only` (all default `False`), an owner `user_id`
  (falsy = shared/team identity) and `login`, and seven abstract hooks
  (`_browse`, `_search`, `_fetch`, `_normalize`, `_match_inbound`, `_send`,
  `_subscribe_push`) that raise `NotImplementedError` on the base -- concrete
  providers (`conversation_imap`, `conversation_gmail`) `_inherit` this model
  and implement the ones their flags claim. `browse_page`/`fetch_envelope`
  are `@api.model` RPC entry points for the inbox viewer; they persist
  nothing.
- `provider` is a `Selection`, not a Many2one against a provider table:
  providers are code, not data, and a table would permit records with no
  implementation behind them. This base module registers no options of its
  own (`selection=[]`) -- each opt-in provider module adds its own via
  `selection_add` (e.g. `conversation_imap` -> `imap`, `conversation_gmail`
  -> `gmail`), so the dropdown only ever offers a provider that is actually
  installed. Storage-compatible with the field's original `Char` (both
  varchar); pre-existing free-text values are normalized to the new keys by
  a migration (`migrations/18.0.1.2.0/`), not silently left invalid.
- `mail.conversation.message_new` is overridden so inbound gateway mail
  builds `mail.conversation.participant` rows from From/To/Cc -- never
  `message_subscribe`/followers.
- `mail.conversation._capture_stub` is the quiet-capture primitive: files an
  inbox stub as a new/existing/linked conversation, posts an internal note
  (`transport_id` falsy) so no external party is re-notified, and maps the
  correspondent to the From partner, never the capturing user.
- `mail.conversation._route_via_alias` feeds a captured raw RFC822 message
  into the ordinary mail gateway so alias routing/threading fire as for a
  real inbound.
- `mail.conversation.action_reply`/`action_forward`/`action_reassign`/
  `action_archive` are the GTD action set's conversation-level primitives;
  outbound delivery always goes through the transport's `_send`, never
  Odoo's notification pipeline.
- A new `ir.rule` scopes `conversation.transport` to each user's own
  (`user_id = uid`) plus shared (`user_id` falsy) transports.
