# Copyright 2026 Bemade Inc. (https://www.bemade.org)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
"""The settings handler.

``res.config.settings`` is already a self-describing, symmetric mapping layer:
``_get_classified_fields()`` sorts every settings field of every installed
module into ``ir.default``, implied groups, module install state,
``ir.config_parameter`` and company-related fields; ``default_get()`` reads
them all back and ``set_values()`` writes them, skipping values that already
match.

So this handler deliberately does NOT re-declare fields. It delegates, and its
whole job is presenting that mapping as a readable document and back. The
payoff is that it extends itself: install an app tomorrow and its settings are
covered without a line of new code here.
"""

from odoo import _

from .handler import Handler, register

#: Fields on the transient itself, never configuration.
TECHNICAL_FIELDS = frozenset({
    "id", "display_name", "create_uid", "create_date",
    "write_uid", "write_date", "company_id",
})

#: Reasons a field is left out. Every exclusion names one, so that a field
#: missing from the document is always a decision on record and never an
#: accident -- which is the difference between a curated export and a lossy one.
RULE_TECHNICAL = "technical-field"
RULE_READONLY = "readonly-display"
RULE_UNRESOLVABLE_REF = "many2one-without-natural-key"


def _normalise(value):
    """Collapse Odoo's interchangeable spellings of "empty".

    ``default_get`` may return ``None`` where a written value would be
    ``False`` (and vice versa) for empty relational and text fields. Comparing
    them raw makes a re-apply of an instance's own settings report a phantom
    change, which would break the idempotence guarantee for no real reason.
    """
    if value is None:
        return False
    if isinstance(value, (list, tuple)):
        return tuple(value)
    return value


@register
class SettingsHandler(Handler):

    domain = "settings"
    order = 40

    # -- reading ---------------------------------------------------------

    def read(self, env, report):
        settings = env["res.config.settings"]
        names = self._configuration_fields(settings, report)
        values = settings.default_get(list(names))
        out = {}
        for name in sorted(names):
            field = settings._fields[name]
            value = values.get(name)
            if field.type == "many2one":
                # An id is meaningless in another database. Until a descriptor
                # can turn it into a natural key we refuse to emit it, and say
                # so, rather than writing a number that will silently apply to
                # the wrong record elsewhere.
                if value:
                    report.skip(self.domain, name, RULE_UNRESOLVABLE_REF)
                    continue
                value = False
            out[name] = value
        return out

    def _configuration_fields(self, settings, report):
        """Field names this handler considers configuration.

        Every field of ``res.config.settings`` is either returned here or
        recorded as skipped with the rule that excluded it.
        """
        keep = set()
        for name, field in settings._fields.items():
            if name in TECHNICAL_FIELDS:
                report.skip(self.domain, name, RULE_TECHNICAL)
                continue
            if field.readonly and not field.inverse and not field.related:
                # Banners, computed hints and other display-only helpers.
                report.skip(self.domain, name, RULE_READONLY)
                continue
            keep.add(name)
        return keep

    # -- writing ---------------------------------------------------------

    def write(self, env, data, report, dry_run=False):
        if not data:
            return
        settings = env["res.config.settings"]
        current = settings.default_get(list(settings._fields))

        vals, unknown = {}, []
        for name, wanted in data.items():
            if name not in settings._fields:
                # The document describes a setting this instance does not
                # have, i.e. its module is not installed. Applying a config to
                # the wrong instance must not look like success.
                unknown.append(name)
                continue
            if _normalise(current.get(name)) != _normalise(wanted):
                report.change(self.domain, name, current.get(name), wanted)
                vals[name] = wanted

        if unknown:
            report.gap(self.domain, _(
                "settings not present on this instance (their modules are not "
                "installed): %(names)s", names=", ".join(sorted(unknown)),
            ))

        if vals and not dry_run:
            # execute() runs set_values() and triggers module installs. Odoo
            # already skips writes for values that match, so passing only the
            # differing keys is an optimisation, not the thing that makes this
            # idempotent.
            settings.create(vals).execute()
