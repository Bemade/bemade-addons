{
    "name": "Instance Configuration as Code",
    "version": "19.0.1.9.0",
    "summary": "Read and write an instance's configuration as a readable YAML "
               "file, idempotently and symmetrically",
    "description": """
Declarative Instance Configuration
==================================

Reads and writes the configuration of an Odoo instance as a single readable
YAML file, so that setting up an instance is *data* rather than a hand-written
module repeated once per project.

Both directions, one definition
-------------------------------

Configuration is handled by **handlers**, each owning one domain (companies,
users and rights, modules, mail servers, accounting, ...) and implementing
**both** directions:

``write``
    apply the declaration to this instance, idempotently

``read``
    snapshot this instance back into the same declaration

The two are written together, as one definition of what the domain *is*. That
is what makes the useful operation possible: point the reader at an instance
that was configured by hand, get the canonical file out, review it, commit it,
and replay it anywhere. No one has to organise the configuration by hand.

The governing invariant is the **round trip**: reading an instance, writing the
result to a fresh instance, and reading that one again must produce the same
file. A domain that cannot round-trip has a missing or lossy handler, and the
test suite says so.

Generic and specialised handlers
--------------------------------

Generic handlers -- companies, users, groups, module state,
``ir.config_parameter``, ``ir.default``, mail servers -- ship here. Specialised
ones, such as the accounting chart, taxes and fiscal positions, live in bridge
modules that depend on this one and on the application they configure, so this
module stays installable anywhere.

Why not ``res.config.settings``
-------------------------------

``res.config.settings`` is a TransientModel and reaches only a fraction of what
actually constitutes an instance's configuration. The settings that matter are
spread across company columns, group membership and implied groups, module
install state, ``ir.default``, ``ir.config_parameter``, mail servers, users and
the accounting setup. This module owns the translation from a readable
declaration down to those substrates.

A readable layer, not a model dump
----------------------------------

The file is written to be read by a person::

    features:
      analytic_accounting: on
      unsplash_images: off

    accounting:
      tax_registrations: [gst, qst]

The value of this module is not the loader, which is small. It is the curated
mapping from human-meaningful statements to the technical records that
implement them.

Derived configuration
---------------------

Where a body of rules determines the answer, the file states the *facts* and
the loader derives the configuration. Declaring which sales-tax registrations a
company holds is enough to determine the correct tax in every jurisdiction it
sells into; the matrix is derived rather than retyped, and can still be
overridden explicitly where reality disagrees.

Secrets
-------

Secret values are never written in the file. They are referenced::

    password: !secret mail.outgoing.primary

and resolved at load time from a mounted file or the environment, so the
configuration itself is safe to commit, diff and review.

Idempotence
-----------

Applying the same file twice changes nothing the second time. The loader
reports what it changed, supports a dry run, and refuses to proceed rather than
silently doing half the work.
""",
    "author": "Bemade Inc.",
    "maintainer": "Marc Durepos <marc@bemade.org>",
    "website": "https://www.bemade.org",
    "license": "LGPL-3",
    "category": "Technical",
    "depends": ["base"],
    "external_dependencies": {"python": ["pyyaml"]},
    "data": [],
    "installable": True,
    "application": False,
}
