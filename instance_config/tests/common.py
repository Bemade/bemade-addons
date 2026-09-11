# Copyright 2026 Bemade Inc. (https://www.bemade.org)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
"""Shared fixtures for instance_config tests.

The environment save/restore helper follows the precedent in
``bemade_sql_console/tests/common.py``, which is the existing in-house way to
test code that reads credentials from ``os.environ``.
"""

import os
import tempfile
from contextlib import contextmanager

import yaml

from odoo.tests import TransactionCase


class InstanceConfigCase(TransactionCase):

    @contextmanager
    def patched_environ(self, **values):
        """Set env vars for the block, restoring the previous state after.

        Keys that were absent are DELETED on exit rather than set to '' -- an
        empty variable left behind would make a later "missing secret"
        assertion pass for the wrong reason.
        """
        missing = object()
        previous = {k: os.environ.get(k, missing) for k in values}
        os.environ.update(values)
        try:
            yield
        finally:
            for key, old in previous.items():
                if old is missing:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = old

    def secrets_file(self, mapping):
        """Write ``mapping`` to a temp YAML file, return a ``file:`` spec."""
        handle = tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False)
        with handle as fh:
            yaml.safe_dump(mapping, fh)
        self.addCleanup(os.unlink, handle.name)
        return f"file:{handle.name}"
