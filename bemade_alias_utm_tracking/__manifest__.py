# -*- coding: utf-8 -*-
{
    "name": "Mail Alias UTM Source Tracking",
    "version": "18.0.1.0.0",
    "category": "Marketing/Email Marketing",
    "summary": "Attribute records created from an inbound mail alias to a UTM "
    "source/medium/campaign, and carry it to leads created from tickets.",
    "description": """
Mail Alias UTM Source Tracking
==============================

Lets you flag, per ``mail.alias``, that records created from inbound mail to
that alias should be attributed to a UTM source (and, optionally, medium and
campaign).

* Adds ``track_utm_source`` (boolean) plus ``utm_source_id``,
  ``utm_medium_id`` and ``utm_campaign_id`` to ``mail.alias``.
* When a record is created from inbound mail to a tracking alias, the
  configured UTM values are stamped onto the new record (any alias target
  model that carries the ``utm.mixin`` fields ``source_id`` / ``medium_id`` /
  ``campaign_id`` — e.g. ``helpdesk.ticket`` and ``crm.lead``).
* The Enterprise "Convert to lead" wizard already copies these fields from the
  ticket to the lead, so a source set on a ticket carries through on
  conversion. This module's tests assert that end-to-end behaviour.
    """,
    "author": "Bemade Inc.",
    "website": "https://www.bemade.org",
    "license": "LGPL-3",
    "depends": [
        "mail",
        "utm",
        # crm_helpdesk pulls in crm + helpdesk and provides the
        # "Convert to lead" wizard (helpdesk.ticket.to.lead) that already copies
        # source/medium/campaign from the ticket to the lead — the ticket->lead
        # transfer this module relies on (and tests end-to-end).
        "crm_helpdesk",
    ],
    "data": [
        "views/mail_alias_views.xml",
    ],
    "installable": True,
    "application": False,
}
