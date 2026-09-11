# Copyright 2026 Bemade Inc. (https://www.bemade.org)
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl-3.0).
"""The entry point: ``env["instance.config"]``.

Applying a configuration is a deployment step, taken deliberately with the
secret mounted, after the modules are installed -- not something a module
does to the database as a side effect of being installed. So this is a
method to call, from ``odoo shell``, an RPC client, or an operator's init
job::

    env["instance.config"].apply_file("my_module/config/instance.yaml")
    env["instance.config"].export()          # -> readable YAML text
"""

import logging

from odoo import api, models
from odoo.tools import file_open

from ..tools import engine
from ..tools.secrets import dump_document, load_document

_logger = logging.getLogger(__name__)


class InstanceConfig(models.AbstractModel):
    _name = "instance.config"
    _description = "Instance configuration as code"

    @api.model
    def apply_document(self, document, dry_run=False):
        """Apply a parsed document. Returns the change report."""
        report = engine.write(self.env, document, dry_run=dry_run)
        _logger.info("instance.config: %s%s", report.summary(),
                     " (dry run)" if dry_run else "")
        for domain, detail in report.unhandled:
            _logger.warning("instance.config: [%s] %s", domain, detail)
        return report

    @api.model
    def apply_text(self, text, dry_run=False):
        return self.apply_document(load_document(text), dry_run=dry_run)

    @api.model
    def apply_file(self, path, dry_run=False):
        """``path`` is module-relative, as accepted by ``odoo.tools.file_open``."""
        with file_open(path) as fh:
            return self.apply_text(fh.read(), dry_run=dry_run)

    @api.model
    def export(self, readable=True):
        """The instance's configuration as YAML text."""
        document, report = engine.read(self.env, readable=readable)
        for domain, detail in report.unhandled:
            _logger.warning("instance.config: [%s] %s", domain, detail)
        return dump_document(document)
