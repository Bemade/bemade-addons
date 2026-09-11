# Copyright 2026 Bemade Inc. (https://www.bemade.org)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
"""The readable layer.

The handlers work on a canonical document keyed by model name and field name.
People do not want to read `ir.mail_server[0].smtp_pass`; they want
`mail.outgoing[0].password`. This module translates between the two.

It is sugar, and optional in both directions: a document may use either form,
and a setting or field with no alias simply keeps its canonical name. That is
what keeps the export complete -- nothing is dropped for lack of a pretty name.

`rights:` bundles are write-side only. They expand into `group_ids` on each
user that names one, so "same rights as X" is stated once; on read the groups
come back explicit, because a set of groups does not remember which bundle it
came from.
"""

import copy

import yaml

from odoo import _
from odoo.exceptions import UserError
from odoo.tools import file_open


def load_aliases(path="instance_config/data/aliases.yaml"):
    with file_open(path) as fh:
        return yaml.safe_load(fh) or {}


def _get_path(doc, dotted):
    node = doc
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def _pop_path(doc, dotted):
    parts = dotted.split(".")
    node = doc
    for part in parts[:-1]:
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    if not isinstance(node, dict):
        return None
    value = node.pop(parts[-1], None)
    # drop emptied containers so `mail: {}` does not linger
    if not node and len(parts) > 1:
        _pop_path(doc, ".".join(parts[:-1]))
    return value


def _set_path(doc, dotted, value):
    parts = dotted.split(".")
    node = doc
    for part in parts[:-1]:
        node = node.setdefault(part, {})
    node[parts[-1]] = value


def to_canonical(document, aliases=None):
    """Readable -> canonical. Returns a new document; the input is untouched."""
    aliases = aliases or load_aliases()
    doc = copy.deepcopy(document)

    # rights bundles -> group_ids
    bundles = doc.pop("rights", None) or {}
    users_key = next(
        (k for k, v in (aliases.get("sections") or {}).items() if v == "res.users"),
        "res.users")
    users = _get_path(doc, users_key) or doc.get("res.users") or []
    # NB: not `user` -- odoo's _() inspects the caller's frame for a local of
    # that name to pick a language, and calls int() on it.
    for entry in users:
        if isinstance(entry, dict) and "rights" in entry:
            name = entry.pop("rights")
            if name not in bundles:
                raise UserError(_(
                    "user %(login)s names rights bundle %(name)r, which the "
                    "document does not define.",
                    login=entry.get("login"), name=name))
            entry.setdefault("groups", list(bundles[name]))

    # sections
    for readable, canonical in (aliases.get("sections") or {}).items():
        value = _pop_path(doc, readable)
        if value is not None:
            doc[canonical] = value

    # fields
    for canonical, fmap in (aliases.get("fields") or {}).items():
        entries = doc.get(canonical)
        if not isinstance(entries, list):
            continue
        for entry in entries:
            for readable, field in fmap.items():
                if readable in entry:
                    entry[field] = entry.pop(readable)

    # features -> settings
    features = doc.pop("features", None) or {}
    fmap = aliases.get("features") or {}
    settings = doc.setdefault("settings", {})
    for readable, value in features.items():
        if readable not in fmap:
            raise UserError(_(
                "feature %(name)r has no known setting behind it.", name=readable))
        settings[fmap[readable]] = value
    if not settings:
        doc.pop("settings")
    return doc


def to_readable(document, aliases=None):
    """Canonical -> readable. The inverse of :func:`to_canonical`."""
    aliases = aliases or load_aliases()
    doc = copy.deepcopy(document)

    # settings -> features, for the aliased ones only
    reverse = {v: k for k, v in (aliases.get("features") or {}).items()}
    settings = doc.get("settings") or {}
    features = {}
    for field in list(settings):
        if field in reverse:
            features[reverse[field]] = settings.pop(field)
    if features:
        doc["features"] = features
    if "settings" in doc and not doc["settings"]:
        doc.pop("settings")

    # fields
    for canonical, fmap in (aliases.get("fields") or {}).items():
        entries = doc.get(canonical)
        if not isinstance(entries, list):
            continue
        rmap = {v: k for k, v in fmap.items()}
        for entry in entries:
            for field, readable in rmap.items():
                if field in entry:
                    entry[readable] = entry.pop(field)

    # sections
    for readable, canonical in (aliases.get("sections") or {}).items():
        if canonical in doc:
            _set_path(doc, readable, doc.pop(canonical))
    return doc
