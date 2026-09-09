Gmail `conversation.transport` provider (task #3965). Opt-in: install this
module to browse/send through a Gmail account in-Odoo, authenticated with
OAuth2/XOAUTH2 -- no password is ever stored (Gmail killed app-passwords).

## Why

Depends on `conversation_email_base` and reuses its browse/search/fetch/
normalize/match/send implementation as-is -- Gmail is IMAP under the hood,
so there is exactly one implementation of each, not a second copy. This
module supplies only what actually differs: OAuth credentials/tokens
(`google.gmail.mixin`'s XOAUTH2, RFC 7628 -- Odoo's own Gmail OAuth
scaffolding, reused rather than reimplemented) and the two hooks the engine
asks a provider for -- `_email_connection_params()` (Gmail's fixed
endpoints, and no password) and `_imap_oauth_string()` (authenticate with a
token instead of a password).

`conversation_imap` is deliberately **not** a dependency: a Gmail-only
deployment has no reason to install generic IMAP/SMTP credential support.
The two providers are siblings on the shared engine, and every override
here is guarded on the record's `provider` value, so they cannot shadow
each other whatever order Odoo loads them in.

The user types neither a host nor a login: `imap.gmail.com`/`smtp.gmail.com`
are the provider's own constants, and `login` is derived from Google's own
userinfo response for the connected account the moment it connects. This is
also what fixes the original "Configure the IMAP host and login" crash on
browsing a connected Gmail account (task #3965 staging-review, 2026-08-13):
that bug was two provider modules each independently overriding the same
method names (`_browse`, `_imap_connection`, ...) on the shared
`conversation.transport` model, with whichever module happened to load last
clobbering the other's implementation for every transport, Gmail included.
Dispatching on `provider` from a single shared engine removes that hazard
structurally, without either provider having to depend on the other.

## Per-account OAuth credentials (AC4)

`client_id`/`client_secret` on the account override the instance-wide
`google_gmail_client_id`/`google_gmail_client_secret` (Settings ▸ General
Settings ▸ Emails ▸ "Use a Gmail Server") when set, falling back to them
otherwise. One Gmail provider, not two: a Google Workspace org shares the
instance-wide pair (the common case, both fields left blank on the account);
an individual user connecting a personal Gmail account brings their own
Google Cloud OAuth client instead. Both resolve correctly side by side on
the same instance. `client_secret` is `groups="base.group_system"`, matching
the OAuth token fields -- a credential, not readable by an ordinary user.

## Known limitation -- admin-only OAuth connect

`google.gmail.mixin`'s OAuth fields (`google_gmail_refresh_token` and
friends) are `groups='base.group_system'`, and `open_google_gmail_uri()`
explicitly requires `base.group_system` -- this mixin was built for a
single shared company mail server (`ir.mail_server`/`fetchmail.server`),
configured once by an administrator. Reused here for a *per-user* personal
Gmail transport, that means only an administrator can actually run the
"Connect to Gmail" OAuth flow on a `conversation.transport` record today,
even though the record itself may carry a `user_id` (i.e. any user's
Settings ▸ My Mail Accounts transport must currently be connected *for*
them by an admin, not by the user themselves). This is a real product gap
against the design's "a user can connect their own mail account(s)" intent
(AC4) -- flagged in the task's implementation notes for a follow-up
decision (e.g. a thin controller that lets a user complete their own
consent flow while still writing the group_system-restricted token fields
via `sudo()`).

## Prerequisite -- OAuth Client ID/Secret (instance-wide or per-account)

Before *any* account can be connected, either the account itself needs its
own Client ID/Secret (see above), or an administrator must register a
Google OAuth Client ID/Secret for the whole instance under Settings ▸
General Settings ▸ Emails ▸ Custom Email Servers ▸ Use a Gmail Server (this
sets the `google_gmail_client_id`/`google_gmail_client_secret`
`ir.config_parameter`s `google.gmail.mixin` falls back to). If neither is
configured, clicking "Connect to Gmail" on a `conversation.transport` record
raises a `RedirectWarning` that takes the admin straight to General
Settings with an explanation, instead of the bare "Please configure your
Gmail credentials." dead end the mixin raises by default (task #3965
staging-review fix, 2026-08-13). Registering the Google Cloud OAuth app
itself (the actual Client ID/Secret values) is a one-time, per-client/
per-instance ops task, not something any module can do for you.

## Security note

This module defines no password field and never reads one: its
`_email_connection_params()` returns `password: None`, so the engine always
takes the XOAUTH2 path, built fresh per connection from
`google.gmail.mixin`'s OAuth tokens. (Installing `conversation_imap`
alongside adds a `password` column to the shared `conversation.transport`
model for *its* transports; a Gmail account neither shows it nor uses it.)
`client_secret` is field-security restricted like the OAuth tokens (see
above).

## Upgrade note (18.0.2.0.0)

The shared IMAP/SMTP implementation moved out of `conversation_imap` into a
new `conversation_email_base`, which this module now depends on instead --
so a Gmail-only deployment no longer installs generic IMAP support. Gmail's
endpoints stop being stored on the record (`imap_host`/`imap_port`/
`smtp_host`/`smtp_port` are `conversation_imap`'s fields, for its own
transports) and come from `_email_connection_params()` instead. Nothing to
migrate: those values were constants either way, and `login` is untouched.
