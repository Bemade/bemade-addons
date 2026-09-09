#    Bemade Inc.
#
#    Copyright (C) 2026-today Bemade Inc. (<https://www.bemade.org>).
#    Author: Marc Durepos (Contact : marc@bemade.org)
#
#    This program is under the terms of the GNU Lesser General Public License (LGPL-3)
#    For details, visit https://www.gnu.org/licenses/lgpl-3.0.en.html

{
    "name": "Kubernetes Health Check",
    "version": "18.0.1.0.0",
    "license": "LGPL-3",
    "development_status": "Beta",
    "category": "Technical",
    "summary": "Health check endpoint for Kubernetes liveness/readiness probes",
    "author": "Bemade Inc.",
    "website": "https://www.bemade.org",
    "depends": ["base"],
    "description": """
Kubernetes Health Check
=======================

Exposes a health check endpoint for Odoo deployments running under Kubernetes.

Odoo's built-in ``/web/health`` only proves the HTTP worker is answering. It
keeps returning 200 while the application is unable to serve real requests --
most importantly after a PostgreSQL primary fails over to a replica, when
existing workers retain stale connections that look valid but fail on the first
query. This module's endpoint exercises the dependencies instead of the socket.

Endpoint
--------

``GET|HEAD /health/ready`` (``auth="none"``) returns:

* **HTTP 200** with a JSON body when every check passes
* **HTTP 503** with a JSON body when any check fails

Checks performed:

* the database connection is live -- executes ``SELECT 1`` inside a savepoint
* the filestore is writable -- creates, writes and unlinks a temporary file

The JSON body carries the diagnostic detail::

    {
      "status": "healthy",
      "database": {"ok": true, "time_ms": 1.2},
      "filestore": {"ok": true}
    }

Configuration
-------------

Point the readiness probe of the deployment at the endpoint::

    readinessProbe:
      httpGet:
        path: /health/ready
        port: 8069
      periodSeconds: 10
      timeoutSeconds: 2
      failureThreshold: 3

Under the Bemade ``odoo-operator`` this is ``spec.probes.readinessPath`` on the
``OdooInstance`` resource, which otherwise defaults to ``/web/health``.

Install the module and confirm the endpoint answers 200 **before** pointing a
readiness probe at it -- a readiness probe against a route that does not resolve
takes the pod out of service.

The endpoint is equally usable for the liveness and startup probes. Prefer a
separate ``Job`` for major upgrades rather than widening probe tolerance.

Notes
-----

* Access logs for ``/health/ready`` are suppressed via a ``logging.Filter`` on
  the ``werkzeug`` logger, to keep frequent probes out of the log.
* Use the probe's own ``timeoutSeconds`` to bound how long the checks may take.
""",
    "installable": True,
    "application": False,
}
