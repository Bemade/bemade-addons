# Copyright 2026 Bemade Inc. (https://www.bemade.org)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
"""Record descriptors and field inference.

Settings are covered generically by ``res.config.settings``. Records are not:
which of an instance's records constitute *configuration* is a judgement no
metadata encodes, so it has to be curated.

What does NOT have to be curated is the field list. That is inferred from the
model's ``_fields``, so a descriptor names only the exceptions -- about five
lines per model, never one per field. Adding a model needs no Python.
"""

import yaml

from odoo import _
from odoo.exceptions import UserError
import base64

from odoo.tools import file_open

from odoo.fields import Command

from .handler import Handler
from .secrets import SecretRef

RULE_SECRET_KEPT = "secret-unresolved-existing-value-kept"

#: Never configuration, on any model.
AUDIT_FIELDS = frozenset({
    "id", "display_name", "create_uid", "create_date",
    "write_uid", "write_date", "__last_update",
})

RULE_AUDIT = "audit-field"
RULE_COMPUTED = "computed-without-inverse"
RULE_INVERSE_O2M = "inverse-one2many"
RULE_BINARY = "binary-not-included"
RULE_EXCLUDED = "excluded-by-descriptor"
RULE_M2M_OTHER_SIDE = "many2many-carried-by-the-other-side"


def load_descriptors(path="instance_config/data/descriptors.yaml"):
    with file_open(path) as fh:
        return yaml.safe_load(fh) or {}


def _write_password_hash(env, user, value, report):
    """Store a pre-computed hash so the user's existing password keeps working.

    res.users.password is a compute that reads back empty and an inverse that
    HASHES whatever it is given -- so handing it a hash would hash the hash.
    The column has to be written directly. A null means "legitimately no
    password": the user is created without one and must go through a reset,
    which is reported rather than papered over.
    """
    if not user:
        return
    if value is None:
        report.skip("res.users", f"{user.login}.password_hash",
                    "no-password-on-record")
        return
    env.cr.execute(
        "UPDATE res_users SET password = %s WHERE id = %s", (value, user.id))
    user.invalidate_recordset(["password"])


#: (model, field) -> writer, for fields the ORM cannot write correctly.
SPECIAL_FIELDS = {
    ("res.users", "password_hash"): _write_password_hash,
}


class Descriptor:
    """One model's configuration description."""

    def __init__(self, model, spec, registry=None):
        self.registry = registry
        self.model = model
        self.key = spec["key"]
        #: field whose value narrows the key: journals are keyed by `code`,
        #: unique only within a company, so `scope: company_id`.
        self.scope = spec.get("scope")
        self.order = spec.get("order", 100)
        #: referenced by other models, never written by the loader
        self.readonly = bool(spec.get("readonly"))
        self.include = set(spec.get("include") or ())
        self.exclude = set(spec.get("exclude") or ())
        self.secret = set(spec.get("secret") or ())

    def _other_side_carries(self, field):
        """True when the counterpart model is described and applied later."""
        if self.registry is None or field.comodel_name == self.model:
            return False
        other = self.registry.get(field.comodel_name)
        return other is not None and other.order > self.order

    def infer_fields(self, env, report=None):
        """Field names to carry for this model.

        Inference, in order: drop audit fields; drop anything the descriptor
        excludes; drop computed fields with no inverse (nothing to write back
        to); drop one2many fields, which are the inverse of a many2one that the
        other side already carries -- keeping both would store the same
        relationship twice and let the two disagree; drop binaries unless the
        descriptor asks for them, since most are large and few are config.
        """
        model = env[self.model]
        keep = []
        for name, field in sorted(model._fields.items()):
            rule = None
            if name in AUDIT_FIELDS:
                rule = RULE_AUDIT
            elif name in self.exclude:
                rule = RULE_EXCLUDED
            elif field.type == "one2many":
                rule = RULE_INVERSE_O2M
            elif field.inherited or (field.related and not field.readonly):
                # Delegated (res.users -> res.partner) and writable related
                # fields are not stored on this model but ARE configuration
                # and ARE writable through it. Keep them, ahead of the store
                # check that would otherwise drop them.
                rule = None
            elif not field.store:
                rule = RULE_COMPUTED
            elif field.compute and field.readonly and not field.inverse and not field.related:
                # A compute is dropped only when it cannot be written to.
                # A stored compute declared readonly=False -- account.journal
                # `code`, precomputed from the name -- takes a written value
                # and keeps it, and IS configuration.
                rule = RULE_COMPUTED
            elif field.type == "binary" and name not in self.include:
                rule = RULE_BINARY
            elif field.type == "many2many" and self._other_side_carries(field):
                # A many2many is one relationship stored on two sides. Carry it
                # on the side applied LATER, so the records it points at
                # already exist; carrying both would store the same fact twice
                # and let the two copies disagree.
                rule = RULE_M2M_OTHER_SIDE
            if rule and name not in self.include:
                if report is not None:
                    report.skip(self.model, name, rule)
                continue
            keep.append(name)
        return keep


XMLID = "xmlid"


def key_of(env, record, key):
    """The natural key of ``record`` under ``key`` (a field name, or XMLID)."""
    if key == XMLID:
        data = env["ir.model.data"].sudo().search([
            ("model", "=", record._name), ("res_id", "=", record.id),
        ], limit=1, order="id")
        return f"{data.module}.{data.name}" if data else None
    return record[key]


def find_by_key(env, model_name, key, value, scope=None):
    """Look a record up by natural key; archived records included.

    ``scope`` is an optional ``(field, id)`` narrowing the search -- the
    company a journal code belongs to.
    """
    if key == XMLID:
        return env.ref(value, raise_if_not_found=False) or env[model_name]
    domain = [(key, "=", value)]
    if scope:
        domain.append((scope[0], "=", scope[1]))
    return env[model_name].with_context(active_test=False).search(domain, limit=1)


class DescriptorRegistry:
    """The descriptor table, with cross-model validation."""

    def __init__(self, specs):
        self.by_model = {}
        for model, spec in specs.items():
            self.by_model[model] = Descriptor(model, spec, registry=self)

    def get(self, model):
        return self.by_model.get(model)

    def validate(self, env):
        """Check that every many2one target is describable and ordered first.

        Caught at load time rather than halfway through an apply: a document
        that cannot possibly be applied should fail before it has written
        anything.
        """
        problems = []
        for descriptor in self.by_model.values():
            if descriptor.model not in env or descriptor.readonly:
                # Read-only descriptors are reference-only: never written, so
                # never ordered. They exist to give pointed-at records a key.
                continue
            model = env[descriptor.model]
            for name in descriptor.infer_fields(env):
                field = model._fields[name]
                if field.type not in ("many2one", "many2many"):
                    continue
                if field.comodel_name == descriptor.model:
                    # A self-reference (res.company.parent_id) cannot be
                    # ordered before itself. It is applied in a second pass
                    # once every record of the model exists -- see
                    # RecordHandler.write.
                    continue
                target = self.get(field.comodel_name)
                if target is None:
                    continue        # reported at read time, per-value
                # A forward reference (res.company.intercompany_user_id ->
                # res.users, applied later) is deferred to the end of the
                # whole apply, once every section has run. See
                # RecordHandler.write / apply_deferred. Nothing to check.
        if problems:
            raise UserError("\n".join(problems))


class RecordHandler(Handler):
    """Reads and writes the records of one described model."""

    def __init__(self, descriptor, registry):
        self.descriptor = descriptor
        self.registry = registry
        self.domain = descriptor.model
        self.order = descriptor.order

    # -- helpers ---------------------------------------------------------

    def _natural_key(self, record):
        return key_of(record.env, record, self.registry.get(record._name).key)

    def _gap_once(self, report, field, message):
        seen = getattr(self, "_gaps_reported", None)
        if seen is None:
            seen = self._gaps_reported = set()
        if field not in seen:
            seen.add(field)
            report.gap(self.domain, message)

    def _emit_value(self, env, record, name, report):
        field = record._fields[name]
        value = record[name]
        if name in self.descriptor.secret:
            if not value:
                return False
            return SecretRef(f"{self.descriptor.model}.{self._natural_key(record)}.{name}")
        if field.type == "many2one":
            if not value:
                return False
            target = self.registry.get(field.comodel_name)
            if target is None:
                # Emitting a raw id would silently bind this document to one
                # database. Refuse, and make the gap visible -- once per
                # field, not once per record, or a model with a hundred rows
                # buries the report.
                self._gap_once(report, name, _(
                    "%(field)s references %(model)s, which has no descriptor; "
                    "cannot express it as a natural key.",
                    field=name, model=field.comodel_name,
                ))
                return None
            return key_of(env, value, target.key)
        if field.type in ("many2many",):
            target = self.registry.get(field.comodel_name)
            if target is None:
                self._gap_once(report, name, _(
                    "%(field)s references %(model)s, which has no descriptor.",
                    field=name, model=field.comodel_name,
                ))
                return None
            keys = [key_of(env, v, target.key) for v in value]
            return sorted(k for k in keys if k)
        return value

    # -- reading ---------------------------------------------------------

    def read(self, env, report):
        model = env[self.descriptor.model]
        names = self.descriptor.infer_fields(env, report)
        out = []
        for record in model.with_context(active_test=False).search([]):
            entry = {}
            identity = key_of(env, record, XMLID)
            if self.descriptor.key == XMLID:
                if not identity:
                    continue            # no external id: not a shipped record
                entry[XMLID] = identity
            elif identity:
                entry[XMLID] = identity     # so a re-apply matches by identity
            for name in names:
                value = self._emit_value(env, record, name, report)
                if value is None:
                    continue
                entry[name] = value
            out.append(entry)
        return out

    # -- writing ---------------------------------------------------------

    def _scope_for(self, env, model, field, entry, existing):
        """The (field, id) scope to resolve ``field``'s target under, if any.

        The target's scope field (company_id) is read off the referring record:
        a company scopes to itself; anything else uses its own company_id,
        from the entry being written or the existing record.
        """
        target = self.registry.get(field.comodel_name)
        if target is None or not target.scope:
            return None
        if model._name == "res.company":
            return (target.scope, existing.id) if existing else None
        if target.scope in model._fields:
            value = entry.get(target.scope) if entry else None
            if isinstance(value, str):
                scope_model = model._fields[target.scope].comodel_name
                scope_desc = self.registry.get(scope_model)
                found = find_by_key(env, scope_model, scope_desc.key, value) if scope_desc else None
                return (target.scope, found.id) if found else None
            if existing and existing[target.scope]:
                return (target.scope, existing[target.scope].id)
        return None

    def _resolve_value(self, env, name, value, model, report, existing=None, entry=None):
        field = model._fields[name]
        if isinstance(value, SecretRef):
            # The engine resolves what it can. A reference reaching here is
            # one it could not resolve. If the record already holds a value,
            # keep it -- re-applying an instance's own configuration must not
            # demand a secrets file for credentials that are already in place.
            # If it holds nothing, this is the silent-blank case: refuse.
            if existing and existing[name]:
                report.skip(self.domain, f"{existing[self.descriptor.key]}.{name}",
                            RULE_SECRET_KEPT)
                return None
            raise UserError(_(
                "%(model)s.%(field)s needs secret %(path)s, which could not be "
                "resolved, and there is no existing value to keep.",
                model=self.descriptor.model, field=name, path=value.path,
            ))
        if field.type == "binary" and isinstance(value, str) and "/" in value:
            # A module-relative path: `my_module/static/img/logo.png`. Read at
            # apply time, so a document can carry a file by reference instead
            # of a base64 blob nobody can review.
            with file_open(value, "rb") as fh:
                return base64.b64encode(fh.read())
        if field.type == "many2many":
            if not value:
                return [Command.clear()]
            target = self.registry.get(field.comodel_name)
            scope = self._scope_for(env, model, field, entry, existing)
            records = env[field.comodel_name]
            missing = []
            for item in value:
                found = find_by_key(env, field.comodel_name, target.key, item, scope)
                if found:
                    records |= found
                else:
                    missing.append(item)
            if missing:
                raise UserError(_(
                    "%(model)s.%(field)s refers to %(target)s %(missing)r, "
                    "which do not exist.",
                    model=self.descriptor.model, field=name,
                    target=field.comodel_name, missing=sorted(missing),
                ))
            return [Command.set(records.ids)]
        if field.type == "many2one":
            if not value:
                return False
            target = self.registry.get(field.comodel_name)
            scope = self._scope_for(env, model, field, entry, existing)
            # Archived records are legitimate targets
            # (res.users.main_user_id -> __system__); find_by_key includes them.
            found = find_by_key(env, field.comodel_name, target.key, value, scope)
            if not found:
                raise UserError(_(
                    "%(model)s.%(field)s refers to %(target)s %(value)r, "
                    "which does not exist.",
                    model=self.descriptor.model, field=name,
                    target=field.comodel_name, value=value,
                ))
            return found.id
        return value

    def _is_self_reference(self, model, name):
        field = model._fields.get(name)
        return (
            field is not None
            and field.type in ("many2one", "many2many")
            and field.comodel_name == self.descriptor.model
        )

    def _is_forward_reference(self, model, name):
        """A reference to a model applied AFTER this one."""
        field = model._fields.get(name)
        if field is None or field.type not in ("many2one", "many2many"):
            return False
        if field.comodel_name == self.descriptor.model:
            return False
        target = self.registry.get(field.comodel_name)
        return target is not None and target.order >= self.descriptor.order

    def write(self, env, data, report, dry_run=False):
        if not data or self.descriptor.readonly:
            return
        model = env[self.descriptor.model]
        key = self.descriptor.key
        seen = set()
        deferred = []
        self.forward = []       # collected for the engine's final pass

        for entry in data:
            identifier = entry.get(key)
            if not identifier:
                raise UserError(_(
                    "A %(model)s entry has no %(key)s; records are matched on "
                    "their natural key, never on position.",
                    model=self.descriptor.model, key=key,
                ))
            seen.add(identifier)
            # An entry may name the record it IS by external id, whatever the
            # descriptor's key. That is how a document says "this company is
            # base.main_company, and its name is ..." -- renaming the record a
            # fresh database already has instead of creating a second one.
            if entry.get(XMLID) and key != XMLID:
                existing = find_by_key(env, self.descriptor.model, XMLID, entry[XMLID])
                if existing:
                    seen.add(key_of(env, existing, key))
            else:
                scope = None
                if self.descriptor.scope and entry.get(self.descriptor.scope):
                    scope_field = model._fields[self.descriptor.scope]
                    scope_desc = self.registry.get(scope_field.comodel_name)
                    holder = find_by_key(env, scope_field.comodel_name,
                                         scope_desc.key, entry[self.descriptor.scope])
                    scope = (self.descriptor.scope, holder.id) if holder else None
                existing = find_by_key(env, self.descriptor.model, key, identifier, scope)
            specials = []

            vals = {}
            for name, value in entry.items():
                if name == XMLID:
                    continue
                if (self.descriptor.model, name) in SPECIAL_FIELDS:
                    # Cannot be written through the ORM; applied once the
                    # record exists (it may be created just below).
                    specials.append((name, value))
                    continue
                if self._is_self_reference(model, name) and value:
                    # Deferred: the record it points at may not exist yet.
                    deferred.append((identifier, name, value))
                    continue
                if self._is_forward_reference(model, name) and value:
                    # Deferred further: its target model has not been applied.
                    self.forward.append((identifier, name, value))
                    continue
                if name not in model._fields:
                    report.gap(self.domain, _(
                        "field %(field)s does not exist on %(model)s",
                        field=name, model=self.descriptor.model))
                    continue
                resolved = self._resolve_value(
                    env, name, value, model, report, existing, entry)
                if resolved is None:
                    continue
                if existing and _same(existing[name], resolved, model._fields[name]):
                    continue
                vals[name] = resolved

            if existing and not vals and not specials:
                continue                        # already correct -- no churn
            if vals or not existing:
                before = "existing" if existing else None
                report.change(self.domain, identifier, before, sorted(vals))
            if dry_run:
                continue
            if existing:
                if vals:
                    existing.write(vals)
                record = existing
            else:
                record = model.create(vals)
            for name, value in specials:
                SPECIAL_FIELDS[(self.descriptor.model, name)](
                    env, record, value, report)

        # Second pass: self-references, now that every record exists.
        self._apply_deferred(env, deferred, report, dry_run)

        # Records present here but absent from the document are REPORTED.

        # Deleting configuration nobody declared is the wrong default: a
        # partial document would quietly destroy the rest of the instance.
        for record in model.with_context(active_test=False).search([]):
            identity = key_of(env, record, key)
            if key_of(env, record, XMLID):
                # Shipped by a module (admin, __system__, the public user):
                # not configuration drift, and not worth a warning per apply.
                continue
            if identity and identity not in seen:
                report.gap(self.domain, _(
                    "%(model)s %(key)r exists on this instance but is not in "
                    "the document; left untouched.",
                    model=self.descriptor.model, key=identity))


    def _apply_deferred(self, env, items, report, dry_run=False):
        """Write (identifier, field, value) triples whose targets now exist."""
        model = env[self.descriptor.model]
        key = self.descriptor.key
        for identifier, name, value in items:
            record = find_by_key(env, self.descriptor.model, key, identifier)
            if not record:
                continue
            resolved = self._resolve_value(env, name, value, model, report, record)
            if _same(record[name], resolved, model._fields[name]):
                continue
            report.change(self.domain, identifier, record[name], resolved)
            if not dry_run:
                record.write({name: resolved})

    def apply_deferred(self, env, report, dry_run=False):
        """Engine hook: forward references, after every section has run."""
        self._apply_deferred(env, getattr(self, "forward", []), report, dry_run)
        self.forward = []


def _same(current, wanted, field):
    """Compare a stored value with a desired one, ignoring spelling of empty."""
    if field.type == "many2one":
        return (current.id or False) == (wanted or False)
    if field.type == "many2many":
        # `wanted` is a Command list; compare against the ids it would set.
        wanted_ids = []
        for cmd in wanted or []:
            if cmd[0] == Command.SET:
                wanted_ids = list(cmd[2])
        return sorted(current.ids) == sorted(wanted_ids)
    if current is None or current is False:
        return wanted in (None, False, "")
    return current == wanted
