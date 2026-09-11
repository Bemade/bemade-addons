# Copyright 2026 Bemade Inc. (https://www.bemade.org)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
"""The engine: runs every handler in order, in both directions.

``read(env)`` snapshots an instance into a document. ``write(env, document)``
applies one. The handlers do the domain work; this module owns what is common
to all of them -- ordering, secret resolution, the dry run, the change report,
and the transaction.
"""

from odoo import _
from odoo.exceptions import UserError

from .aliases import to_canonical, to_readable
from .descriptors import DescriptorRegistry, RecordHandler, load_descriptors
from .handler import Report, handlers as registered_handlers
from .secrets import SecretRef, SecretSource

SCHEMA_VERSION = 1

#: Top-level keys that are not handler domains.
META_KEYS = frozenset({"version", "instance", "secrets"})


class _DryRun(Exception):
    """Raised inside the savepoint to force a rollback after a dry run."""


def all_handlers(env, descriptors=None):
    """Every handler for ``env``, in application order.

    Record handlers are built from the descriptor table, so adding a model to
    that file is enough to bring a handler into existence -- no Python.
    """
    registry = DescriptorRegistry(descriptors or load_descriptors())
    registry.validate(env)
    found = [cls() for cls in registered_handlers()]
    for model, descriptor in registry.by_model.items():
        if model in env and not descriptor.readonly:
            # Reference-only descriptors (countries, currencies, groups) give
            # pointed-at records a natural key; they are not sections of the
            # document, so no handler reads or writes them.
            found.append(RecordHandler(descriptor, registry))
    return sorted(found, key=lambda h: h.order)


def read(env, descriptors=None, readable=False):
    """Snapshot ``env`` into a document. Returns ``(document, report)``.

    ``readable=True`` applies the alias layer, so the export is the form a
    person would write. Either form applies identically.
    """
    report = Report()
    document = {"version": SCHEMA_VERSION}
    for handler in all_handlers(env, descriptors):
        data = handler.read(env, report)
        if data:
            document[handler.domain] = data
    if readable:
        document = to_readable(document)
    return document, report


def write(env, document, dry_run=False, descriptors=None):
    """Apply ``document`` to ``env``. Returns the change report.

    Atomic across every handler EXCEPT the module boundary: module changes are
    marked here but carried out by the next registry update, so they cannot be
    rolled back by this transaction and must be treated as a separate,
    re-runnable phase. Everything else is one savepoint -- a failure partway
    leaves the instance as it was.
    """
    _check_version(document)
    document = to_canonical(document)      # readable and canonical both accepted
    source = SecretSource.from_spec((document.get("secrets") or {}).get("source"))
    report = Report()
    known = {h.domain: h for h in all_handlers(env, descriptors)}

    for key in document:
        if key not in known and key not in META_KEYS:
            # A section nothing can apply is a GAP, never a silent skip: a
            # document describing configuration this instance cannot express
            # must not look as though it applied.
            report.gap(key, _("no handler for section %(key)r", key=key))

    try:
        with env.cr.savepoint():
            for domain, handler in sorted(known.items(), key=lambda kv: kv[1].order):
                data = document.get(domain)
                if data is None:
                    continue
                # Secrets resolve lazily, per section actually being applied,
                # so a partial document never demands credentials it will not
                # use.
                #
                # A dry run does the work for real and then rolls the
                # savepoint back. Handlers are NOT told it is a dry run: a
                # later section must be able to resolve records an earlier
                # one creates, which a skip-the-write dry run cannot offer.
                # The report is identical to a real apply, by construction.
                handler.write(env, _resolve(data, source, domain), report)
            if dry_run:
                raise _DryRun()
    except _DryRun:
        pass
    return report


def _check_version(document):
    version = document.get("version")
    if version != SCHEMA_VERSION:
        raise UserError(_(
            "Unsupported document version %(found)r; this loader understands "
            "version %(known)s.", found=version, known=SCHEMA_VERSION,
        ))


def _resolve(value, source, where):
    """Replace every SecretRef in ``value`` with its resolved secret."""
    if isinstance(value, SecretRef):
        # Resolve what can be resolved. A reference with no source, or one the
        # source does not hold, is passed through untouched: the handler
        # decides whether an existing value on the record makes it harmless
        # (re-applying an instance's own config) or fatal (a fresh record with
        # nothing to fall back on). That judgement needs the record; this
        # function does not have it.
        if source is None:
            return value
        try:
            return source.resolve(value)
        except UserError:
            return value
    if isinstance(value, dict):
        return {k: _resolve(v, source, where) for k, v in value.items()}
    if isinstance(value, list):
        return [_resolve(v, source, where) for v in value]
    return value
