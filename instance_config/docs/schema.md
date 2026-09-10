# Instance configuration file — schema v1

A single YAML file describing what an Odoo instance should _be_. Written to be read by a
person, and both **applied to** and **read back from** an instance by
`bemade_config_loader`.

The reader is what makes this practical: point it at an instance somebody configured by
hand, get the canonical file, review it, commit it, replay it. Nobody has to transcribe
a configuration into a form by hand.

## Principles

1. **Readable statements, not model dumps.** `analytic_accounting: on`, not a record on
   `res.groups.implied_ids`. The loader owns the translation.
2. **State facts, derive consequences.** Where a body of rules determines the answer,
   declare the fact. See _Derived configuration_.
3. **No secrets in the file.** Secret values are `!secret` references resolved at load
   time. The file is safe to commit, diff and review.
4. **Idempotent.** Applying twice changes nothing the second time.
5. **Handles, not database ids.** Records refer to each other by stable keys defined in
   the file.
6. **Symmetric.** Every domain is owned by a handler implementing both `write` (apply)
   and `read` (snapshot). They are written together, as one definition of what the
   domain is.

## The round-trip invariant

The governing property, and the centre of the test suite:

    read(instance) -> file
    write(file, fresh_instance)
    read(fresh_instance) -> the same file

A domain that does not round-trip has a missing or lossy handler. Stating this as an
invariant means new handlers are provably complete rather than complete by inspection,
and it catches the failure mode that matters -- a setting that gets applied but never
read back, so a later export silently drops it.

Two exceptions, both explicit:

- **Secrets** round-trip as their `!secret` reference, never as the value. The reader
  emits the reference and writes the value to a separate secret payload the caller
  handles.
- **Derived configuration** round-trips as the _fact_, not the derivation. An instance
  whose taxes match the derived matrix reads back as `tax_registrations: [gst, qst]`;
  one that deviates reads back with explicit `fiscal_positions` overrides for the
  entries that differ.

## Skeleton

```yaml
version: 1

instance:
  key: acme # short handle, no client name required
  odoo_version: "19.0"

secrets:
  source: file:/run/secrets/odoo-config/secrets.yaml # or env:PREFIX_

companies:
  - key: main # handle referenced elsewhere in this file
    name: "Acme Inc."
    country: CA
    state: QC
    currency: CAD
    logo: static/img/logo.png # path relative to the providing module
    phone: "+1 555-555-5555"
    registry: "1234567890"
    intercompany:
      generate_counterpart: true # NOTE: fires on the RECEIVING company

features:
  analytic_accounting: on
  budgets: on
  documents: on
  push_notifications: off
  unsplash_images: off
  snailmail: off

accounting:
  chart: l10n_ca # or a module-provided chart handle
  tax_registrations: [gst, qst] # facts -> the matrix is derived
  fiscal_positions: # optional; overrides the derived matrix
    ON: hst_13

mail:
  outgoing:
    - key: primary
      name: "Primary"
      host: smtp.example.test
      port: 587
      encryption: starttls
      authentication: login
      user: odoo@example.test
      password: !secret mail.outgoing.primary
      from_filter: example.test
      active: false # deliberate: nothing leaves a test instance
      reason: "test instance -- no outbound mail"
  incoming:
    - key: primary
      type: imap
      server: imap.example.test
      port: 993
      ssl: true
      user: odoo@example.test
      password: !secret mail.incoming.primary

rights: # named bundles, so "same as X" is said once
  full_admin:
    - account.group_account_manager
    - base.group_system
    - base.group_multi_company
  bookkeeper:
    - account.group_account_manager
    - base.group_user

users:
  - login: someone@example.test
    name: "Some One"
    lang: fr_CA
    tz: America/Toronto
    companies: [main]
    default_company: main
    rights: full_admin
    password_hash: !secret users.someone # may be absent -> passwordless
```

## Derived configuration

The clearest case is sales tax. `tax_registrations` states which registrations a company
actually holds; the correct tax in every jurisdiction follows from that plus the tax
law, and does not need retyping per client.

A company registered `[gst, qst]` sells into Canada as:

| Where                      | Tax                 | Why                                                                     |
| -------------------------- | ------------------- | ----------------------------------------------------------------------- |
| Quebec                     | GST 5% + QST 9.975% | both registrations apply                                                |
| Ontario                    | HST 13%             | a GST registrant is an HST registrant; place of supply decides the rate |
| NB / NS / PE / NL          | HST 15%             | same                                                                    |
| AB, BC, MB, SK, NT, NU, YT | GST 5% only         | no provincial registration -> no provincial tax may be charged          |
| Outside Canada             | 0%                  |                                                                         |

The last row of that table is the one hand-written configs get wrong: charging a
provincial sales tax the company cannot remit. Deriving it removes the opportunity.

`fiscal_positions` overrides individual entries where reality disagrees.

## Secrets

`!secret <path>` resolves against the source named in `secrets.source`:

- `file:/path/to/secrets.yaml` — a mounted YAML file, dotted path lookup
- `env:PREFIX_` — environment variables, dots uppercased to underscores

A reference that cannot be resolved is a **hard error**. The loader never substitutes a
blank and continues, because a blank password produces an instance that looks configured
and silently does not work.

A `password_hash` that is legitimately absent is written as `~`, distinct from a missing
secret: the user is created without a password and must go through a reset.

## Features and the auto-install problem

`features: <name>: off` may require an explicit **uninstall**, not merely an omission.
`web_unsplash`, `snailmail` and `snailmail_account` all declare `auto_install: True`
with dependencies satisfied by any instance, so they install themselves. The loader
uninstalls them and verifies afterwards, because a later module-list update can
resurrect them.

## Handlers

Each domain is one handler. Generic handlers ship in this module; specialised ones live
in bridge modules depending on this module and on the application they configure, so
this module remains installable anywhere.

| Handler      | Domain                                                     | Ships in              |
| ------------ | ---------------------------------------------------------- | --------------------- |
| `modules`    | install / uninstall, auto-install fights                   | this module           |
| `companies`  | `res.company` columns, logo, inter-co                      | this module           |
| `features`   | groups, `implied_ids`, `ir.config_parameter`, `ir.default` | this module           |
| `mail`       | `ir.mail_server`, `fetchmail.server`                       | this module           |
| `users`      | `res.users`, `res.partner`, rights bundles                 | this module           |
| `accounting` | chart, taxes, fiscal positions, journals                   | bridge on `account`   |
| `documents`  | folders, tags                                              | bridge on `documents` |

## Application order

Order matters and is fixed by the loader, not by the file:

1. modules (installs and uninstalls; registry reload between)
2. companies
3. accounting (chart, taxes, fiscal positions, journals, defaults)
4. features (groups, `ir.config_parameter`, `ir.default`)
5. mail servers
6. users and rights

## Reporting

The loader returns a change list: what it created, what it updated, what it found
already correct. A dry run produces that list and writes nothing. On failure it raises
with the offending path in the file, rather than leaving a half-configured instance.
