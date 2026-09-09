==============================
Partner Address Ranking
==============================

.. |badge1| image:: https://img.shields.io/badge/licence-LGPL--3-blue.png
    :target: http://www.gnu.org/licenses/lgpl-3.0-standalone.html
    :alt: License: LGPL-3

|badge1|

**Description**
---------------

This module ranks a company's child addresses on sales orders by usage history
and allows explicit favorite overrides for invoice and delivery addresses.

Features:

* **Favorite flags** — ``is_favorite_invoice`` and ``is_favorite_delivery``
  checkboxes on child contact forms.  Only one contact per company per address
  type may hold the flag (Python constraint).
* **Usage-based ranking** — when no favorite is set, the address most
  frequently used on *confirmed* or *done* sales orders for the company is
  chosen first.  Draft and cancelled orders are excluded.
* **Picker ordering** — the *Invoice Address* and *Delivery Address* Many2one
  dropdowns on SO forms surface ranked addresses at the top of the list.
* **Full fallback** — if there is no history and no favorite the module
  delegates transparently to Odoo's stock ``address_get`` logic.
* **Non-destructive** — uninstalling the module reverts all behavior.  No
  usage counters are stored on partner records.

**Configuration**
-----------------

No configuration is required.  Install the module and the behavior is
active immediately for all companies.

To mark a child contact as the default invoice address:

1. Open the contact form of the child (e.g. *Billing Department*).
2. Tick **Default invoice address**.
3. Save.  An error is raised if another sibling already holds the flag.

**Usage**
---------

Create a new quotation or sales order.  The *Invoice Address* and *Delivery
Address* fields are pre-filled according to:

1. The favorite address for the address type (if one is set).
2. The address most used on confirmed / done orders for the company.
3. Odoo's built-in ``address_get`` result as the final fallback.

Opening the address dropdown shows the same ranking at the top of the list.

**Known issues / Roadmap**
--------------------------

* Usage ranking considers *any* contact type ever used in that slot, including
  a generic ``type='contact'``.  This means a previously-used generic contact
  can outrank a sibling explicitly typed ``invoice`` or ``delivery``.  The
  behavior is intentional (history-based) but may surprise users who rely
  heavily on ``type`` filtering.
* Bulk-importing multiple contacts with ``is_favorite_*=True`` for the same
  company in a single transaction will trip the constraint.  Clear the existing
  favorite first.
* Odoo 19 forward-port is out of scope for this module version.

**Bug Tracker**
---------------

Bugs are tracked on `odoo.bemade.org <https://odoo.bemade.org>`_.
In case of trouble, please check there if your issue has already been reported.

**Credits**
-----------

Authors
~~~~~~~

* `Bemade Inc. <https://www.bemade.org>`_

Contributors
~~~~~~~~~~~~

* Marc Durepos <marc@bemade.org>

Maintainers
~~~~~~~~~~~

This module is maintained by Bemade Inc.

.. image:: https://www.bemade.org/logo.png
   :alt: Bemade Inc.
   :target: https://www.bemade.org
