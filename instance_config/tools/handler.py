# Copyright 2026 Bemade Inc. (https://www.bemade.org)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
"""Handler base class and the change report.

A handler owns one configuration domain and implements BOTH directions:

``read``
    snapshot this instance into a declaration

``write``
    apply a declaration to this instance, idempotently

The two are written together, as one definition of what the domain is. That is
what makes the round trip possible, and what stops a setting being applied but
never read back -- the failure mode where a later export silently drops it.
"""

from odoo import _

#: Registry of handler classes, in application order.
_HANDLERS = []


def register(cls):
    """Class decorator adding a handler to the registry."""
    _HANDLERS.append(cls)
    _HANDLERS.sort(key=lambda h: h.order)
    return cls


def handlers():
    """Registered handlers, in application order."""
    return list(_HANDLERS)


class Change:
    """One difference a write made, or would make in a dry run.

    Carrying the before/after lets the caller print a review, and lets tests
    assert that an idempotent re-apply produced NOTHING rather than merely not
    raising.
    """

    __slots__ = ("domain", "key", "before", "after")

    def __init__(self, domain, key, before, after):
        self.domain = domain
        self.key = key
        self.before = before
        self.after = after

    def __repr__(self):
        return f"<Change {self.domain}.{self.key}: {self.before!r} -> {self.after!r}>"

    def __eq__(self, other):
        return (
            isinstance(other, Change)
            and (self.domain, self.key, self.before, self.after)
            == (other.domain, other.key, other.before, other.after)
        )


class Report:
    """The outcome of a read or a write."""

    def __init__(self):
        self.changes = []
        self.skipped = []       # (domain, key, rule) -- excluded ON PURPOSE
        self.unhandled = []     # (domain, detail)    -- a GAP, must be visible

    @property
    def empty(self):
        """True when a write changed nothing -- the idempotence assertion."""
        return not self.changes

    def change(self, domain, key, before, after):
        self.changes.append(Change(domain, key, before, after))

    def skip(self, domain, key, rule):
        self.skipped.append((domain, key, rule))

    def gap(self, domain, detail):
        self.unhandled.append((domain, detail))

    def summary(self):
        return _(
            "%(changed)s change(s), %(skipped)s field(s) skipped by rule, "
            "%(gaps)s unhandled item(s)",
            changed=len(self.changes),
            skipped=len(self.skipped),
            gaps=len(self.unhandled),
        )


class Handler:
    """Base class. Subclasses implement :meth:`read` and :meth:`write`."""

    #: key of this handler's section in the document
    domain = None
    #: application order; lower runs first
    order = 100

    def read(self, env, report):
        """Return this domain's declaration for ``env``."""
        raise NotImplementedError

    def write(self, env, data, report, dry_run=False):
        """Apply ``data`` to ``env``, recording differences in ``report``."""
        raise NotImplementedError
