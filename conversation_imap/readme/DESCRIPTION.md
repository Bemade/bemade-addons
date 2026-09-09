Generic IMAP/SMTP `conversation.transport` provider (task #3965). Opt-in:
install this module to browse a mailbox in-Odoo and send through it, over
plain IMAP/SMTP credentials the user supplies.

## Why

`conversation_base` defines the transport interface only (capability flags
+ abstract hooks); `conversation_email_base` implements that interface once
over IMAP/SMTP. This module is the generic-credentials provider on top of
it, and the portability proof that the interface is not Gmail-specific.

- `browsable`/`searchable`/`sendable` = `True`; `pushable` stays `False`
  (IMAP has no native push here -- polling only).
- Registers `imap` on the shared `provider` Selection (`conversation_base`
  ships no options itself) via `selection_add`.
- Contributes the endpoint configuration -- `imap_host`/`imap_port`/
  `imap_ssl`, `smtp_host`/`smtp_port`/`smtp_ssl` -- and the `password`,
  through `_email_connection_params()`, guarded on its own `provider`
  value so a Gmail (or other provider's) transport is never routed through
  these fields.
- Deliberately does **not** override `_imap_oauth_string`: generic IMAP has
  no OAuth mechanism of its own, so the engine's `None` default (plain
  password login) is the right behaviour here.

Everything else -- `_browse`, `_search_remote`, `_fetch`, `_normalize`,
`_match_inbound`, `_send`, connection handling, the envelope cache -- comes
from `conversation_email_base` and is shared with every other email
provider rather than reimplemented per provider. See that module's README
for why dispatch is on the `provider` value and never on module load order.

## Security note

IMAP still requires a password (there is no universal IMAP OAuth); the
`password` field is an ordinary `Char`, scoped like the rest of
`conversation.transport` by the `conversation_base` `ir.rule` (own + shared
transports only). Prefer `conversation_gmail` (OAuth, no stored password)
wherever the provider supports it.

## Upgrade note (18.0.2.0.0)

The IMAP/SMTP implementation moved to the new `conversation_email_base`
dependency; the `imap_folder` field moved with it. No data migration is
needed -- the columns are unchanged on `conversation_transport`, only which
module declares them. Existing transports keep their configuration.
