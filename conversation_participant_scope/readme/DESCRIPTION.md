Adds per-conversation participant roster scope on top of `conversation_base`:
participants belong to the conversation they're on, not a for-life record
subscription, and what an external recipient sees of the roster is under
explicit control.

## Why

`conversation_base` ships `mail.conversation.participant` decoupled from
`mail.followers`: adding a participant never subscribes anyone. This module
adds the policy layer needed to actually run participation day to day:

- `mail.conversation.participant.receives_updates` -- a plain boolean
  distinguishing an ongoing audience member from a one-off CC. CC-once
  participants (`receives_updates=False`) are included on the message they
  were added for but excluded from future recipient computation, until
  explicitly promoted via `_promote_to_recipient()`.
- `mail.conversation.participant.visibility` -- a per-participant override
  (`auto`/`exposed`/`hidden`) of the conversation's roster-visibility policy.
- `mail.conversation.external_visibility` -- the conversation-level policy
  (`hide_internal`/`full`/`private`) controlling what an external viewer sees
  of the participant/CC list.
- `mail.conversation._add_participant()` / `_add_cc_once()` -- thin wrappers
  over the base `participant._get_or_create()` that additionally set the
  scope fields above. A bare email address with no matching partner never
  creates a `res.partner`, and neither ever calls `message_subscribe`.
- `mail.conversation._participants_visible_to()` -- pure computation of the
  participant recordset a given viewer (a partner, or none for internal/
  system viewers) may see; not a `mail.followers`/`ir.rule` row-level
  security mechanism, just a presentation-layer helper for outbound
  rendering.
- `mail.conversation._next_message_recipients()` -- computes the
  `(partners, email_to)` pair for the next outbound message, excluding
  CC-once participants.

This module ships the model, computation, and a participant-management UI
extension only. The outbound `_notify_get_recipients` override / email
header wiring and inbound routing are delivered by later epics.
