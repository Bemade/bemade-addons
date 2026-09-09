# Copyright 2026 Bemade Inc.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).
import json
import logging
import os
import re
import tempfile
import time

from odoo import http
from odoo.http import Response, request
from odoo.tools import config

_logger = logging.getLogger(__name__)


class HealthCheckLogFilter(logging.Filter):
    """Filter to suppress access logs for health check endpoints."""

    def filter(self, record):
        message = record.getMessage()
        return not re.search(r"(GET|HEAD) /health/ready", message)


# Apply filter to werkzeug logger to suppress health check access logs
logging.getLogger("werkzeug").addFilter(HealthCheckLogFilter())


class HealthController(http.Controller):
    """Health check endpoints for Kubernetes probes."""

    @http.route("/health/ready", auth="none", methods=["GET", "HEAD"], csrf=False)
    def ready(self):
        """
        Readiness probe endpoint.

        Returns HTTP 200 if all checks pass, HTTP 503 otherwise.
        Response body is JSON with diagnostic details.
        """
        db_result = self._check_database()
        fs_result = self._check_filestore()

        all_ok = db_result["ok"] and fs_result["ok"]
        status = "healthy" if all_ok else "unhealthy"
        http_status = 200 if all_ok else 503

        response_data = {
            "status": status,
            "database": db_result,
            "filestore": fs_result,
        }

        return Response(
            json.dumps(response_data),
            status=http_status,
            content_type="application/json",
        )

    def _check_database(self, cr=None):
        """Check database connectivity by executing a simple query."""
        if cr is None:
            cr = request.env.cr
        try:
            start = time.perf_counter()
            with cr.savepoint():
                cr.execute("SELECT 1")
                cr.fetchone()
            elapsed_ms = (time.perf_counter() - start) * 1000
            return {"ok": True, "time_ms": round(elapsed_ms, 2)}
        except Exception as e:
            _logger.warning("Health check database failure: %s", e)
            return {"ok": False, "error": str(e)}

    def _check_filestore(self, dbname=None):
        """Check filestore accessibility by attempting to write a temp file."""
        if dbname is None:
            dbname = request.env.cr.dbname
        try:
            filestore_path = config.filestore(dbname)
            fd, path = tempfile.mkstemp(dir=filestore_path, prefix=".health_check_")
            try:
                os.write(fd, b"health check")
            finally:
                os.close(fd)
                os.unlink(path)
            return {"ok": True}
        except Exception as e:
            _logger.warning("Health check filestore failure: %s", e)
            return {"ok": False, "error": str(e)}
