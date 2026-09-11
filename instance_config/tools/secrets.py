# Copyright 2026 Bemade Inc. (https://www.bemade.org)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
"""Resolution of ``!secret`` references in a configuration document.

The configuration file carries no credential -- only references::

    password: !secret mail.outgoing.primary

which are resolved at load time against a source declared in the document::

    secrets:
      source: file:/run/secrets/odoo-config/secrets.yaml
      source: env:ODOO_CONFIG_

A reference that cannot be resolved is a hard error. We never substitute a
blank and continue: a blank password produces an instance that looks
configured and silently does not work, which is worse than failing loudly.
"""

import os

import yaml

from odoo import _
from odoo.exceptions import UserError


class SecretRef:
    """A ``!secret <path>`` reference, before resolution.

    Carrying the reference as an object rather than a magic string means it
    cannot be confused with a literal value, and that emitting a document is
    a matter of writing the reference back out rather than remembering which
    strings were once secret.
    """

    yaml_tag = "!secret"

    __slots__ = ("path",)

    def __init__(self, path):
        self.path = path

    def __repr__(self):
        # Deliberately shows the PATH, never a value -- this object never
        # holds one. Safe to appear in a traceback.
        return f"SecretRef({self.path!r})"

    def __eq__(self, other):
        return isinstance(other, SecretRef) and other.path == self.path

    def __hash__(self):
        return hash((SecretRef, self.path))


class SecretSource:
    """Resolves :class:`SecretRef` paths against a backing store."""

    def __init__(self, spec):
        self.spec = spec

    @classmethod
    def from_spec(cls, spec):
        """Build a source from a ``scheme:location`` string."""
        if not spec:
            return None
        if spec.startswith("file:"):
            return FileSecretSource(spec[len("file:"):])
        if spec.startswith("env:"):
            return EnvSecretSource(spec[len("env:"):])
        raise UserError(_(
            "Unknown secret source %(spec)r. Expected 'file:<path>' or "
            "'env:<PREFIX_>'.", spec=spec,
        ))

    def resolve(self, ref):
        value = self._lookup(ref.path)
        # An empty string is treated as unresolvable rather than as a valid
        # empty password: an empty credential is never intentional, and
        # accepting it produces the silent half-working instance this class
        # exists to prevent.
        if value is None or value == "":
            raise UserError(_(
                "Secret %(path)s could not be resolved from %(source)s. "
                "Refusing to continue with a blank value.",
                path=ref.path, source=self.spec,
            ))
        return value

    def _lookup(self, path):
        raise NotImplementedError


class FileSecretSource(SecretSource):
    """Dotted-path lookup in a mounted YAML file."""

    def __init__(self, path):
        super().__init__(f"file:{path}")
        self.path = path
        self._data = None

    def _load(self):
        if self._data is None:
            try:
                with open(self.path) as fh:
                    self._data = yaml.safe_load(fh) or {}
            except OSError as exc:
                raise UserError(_(
                    "Secret file %(path)s could not be read: %(error)s",
                    path=self.path, error=exc.strerror or exc,
                )) from None      # `from None` -- the original may quote content
        return self._data

    def _lookup(self, path):
        node = self._load()
        for part in path.split("."):
            if not isinstance(node, dict) or part not in node:
                return None
            node = node[part]
        return node


class EnvSecretSource(SecretSource):
    """Environment-variable lookup, dots uppercased to underscores.

    Follows the precedent in ``bemade_sql_console``: credentials are injected
    into the container and read at runtime rather than stored in the database.
    """

    def __init__(self, prefix):
        super().__init__(f"env:{prefix}")
        self.prefix = prefix

    def _lookup(self, path):
        return os.environ.get(self.prefix + path.replace(".", "_").upper())


class ConfigLoader(yaml.SafeLoader):
    """SafeLoader that understands ``!secret``.

    Subclassed rather than registered globally so that adding this module
    cannot change how unrelated code in the process parses YAML.
    """


def _construct_secret(loader, node):
    return SecretRef(loader.construct_scalar(node))


ConfigLoader.add_constructor("!secret", _construct_secret)


class ConfigDumper(yaml.SafeDumper):
    """SafeDumper that writes ``!secret`` references back out."""


def _represent_secret(dumper, data):
    return dumper.represent_scalar("!secret", data.path)


ConfigDumper.add_representer(SecretRef, _represent_secret)


def load_document(stream):
    """Parse a configuration document, leaving secrets unresolved."""
    return yaml.load(stream, Loader=ConfigLoader)


def dump_document(data):
    """Emit a configuration document, writing secrets as references."""
    return yaml.dump(data, Dumper=ConfigDumper, sort_keys=False,
                     allow_unicode=True, default_flow_style=False)
