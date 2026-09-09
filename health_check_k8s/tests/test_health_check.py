# Copyright 2026 Bemade Inc.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html).
"""
Test cases for health_check_k8s module.

Use Case 1: Healthy System (/health/ready)
==========================================
When database and filestore are accessible, the health check returns success.

Acceptance Criteria:
- Returns HTTP 200 when all checks pass
- Response is JSON with status, database, and filestore details
- Database check includes response time in milliseconds
- Does not require authentication
- Logs are suppressed by default to avoid noise

Use Case 2: Database Failure
============================
When the database connection fails or query times out, the health check
returns unhealthy.

Acceptance Criteria:
- Returns HTTP 503 when database query fails
- Response JSON includes database.ok = false
- Actually executes a query (SELECT 1), not just connection check
- Works for stale connections after PostgreSQL failover

Use Case 3: Filestore Inaccessibility
=====================================
When the filestore becomes inaccessible (NFS mount failure, permissions),
the health check returns unhealthy.

Acceptance Criteria:
- Returns HTTP 503 when filestore is not writable
- Response JSON includes filestore.ok = false
- Check opens a file for writing (not just os.access check)
"""

from unittest.mock import patch

from odoo.tests.common import HttpCase, TransactionCase
from odoo.tools import config

from odoo.addons.health_check_k8s.controllers.health import HealthController


class TestHealthCheckEndpoint(HttpCase):
    """Integration tests for the /health/ready endpoint."""

    def test_healthy_system_returns_200(self):
        """Use Case 1: When all checks pass, return HTTP 200 with JSON."""
        response = self.url_open("/health/ready", timeout=10)
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data["status"], "healthy")
        self.assertTrue(data["database"]["ok"])
        self.assertIn("time_ms", data["database"])
        self.assertTrue(data["filestore"]["ok"])

    def test_healthy_system_no_auth_required(self):
        """Use Case 1: Endpoint does not require authentication."""
        response = self.url_open("/health/ready", timeout=10)
        self.assertEqual(response.status_code, 200)


class TestHealthCheckUnit(TransactionCase):
    """Unit tests for health check methods."""

    def setUp(self):
        super().setUp()
        self.controller = HealthController()

    def test_check_database_success(self):
        """Database check returns ok=True when query succeeds."""
        result = self.controller._check_database(cr=self.env.cr)

        self.assertTrue(result["ok"])
        self.assertIn("time_ms", result)
        self.assertIsInstance(result["time_ms"], float)

    def test_check_database_failure_timeout(self):
        """Use Case 2: Database check returns ok=False when query times out.

        We use PostgreSQL's statement_timeout to simulate a slow/hung database.
        The controller runs SELECT 1, but we patch it to run pg_sleep instead.
        """
        new_cr = self.registry.cursor()
        try:
            new_cr.execute("SET statement_timeout = '1ms'")
            original_execute = new_cr.__class__.execute

            def slow_execute(cr_self, query, *args, **kwargs):
                if query == "SELECT 1":
                    query = "SELECT pg_sleep(0.1)"
                return original_execute(cr_self, query, *args, **kwargs)

            with patch.object(new_cr.__class__, "execute", slow_execute):
                result = self.controller._check_database(cr=new_cr)

            self.assertFalse(result["ok"])
            self.assertIn("error", result)
            self.assertIn("timeout", result["error"].lower())
        finally:
            new_cr.close()

    def test_check_filestore_success(self):
        """Filestore check returns ok=True when path is writable."""
        result = self.controller._check_filestore(dbname=self.env.cr.dbname)

        self.assertTrue(result["ok"])

    def test_check_filestore_failure(self):
        """Use Case 3: Filestore check returns ok=False when path is not writable."""
        with patch.object(config, "filestore", return_value="/nonexistent/path"):
            result = self.controller._check_filestore(dbname=self.env.cr.dbname)

        self.assertFalse(result["ok"])
        self.assertIn("error", result)
