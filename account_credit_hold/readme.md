# Overview

This module adds the notion of placing clients on credit hold to the followup levels from the Odoo Enterprise 
account_followup module. It adds an option to followup levels to mark clients matching the followup criteria as on 
credit hold. This hold restricts the confirmation of new sales orders for these clients.

Accountant and admin users can set a date until which the account hold will be
postponed on a specific partner's form view. This effectively gives clients an extra
grace period, allowing orders to be confirmed until the period ends.

# Change Log
## 15.0.2.0.0 (2023-05-04)

Complete remake of the module, making the "Credit Hold" an action that is either manually or
automatically triggered from the Accounting > Followup Reports section or by setting the automatic application field
on followup levels.

## 15.0.1.1.0 (2023-05-03)

Adds a ribbon to stock pickings for clients on hold, and therefore a dependency on stock.

## 15.0.1.0.2 (2023-05-03)

Fix to sale order view and sale order confirmation for clients not on hold.

## 15.0.1.0.1 (2023-05-03) 

Fix clients on hold when status is "outstanding_invoices".

## 15.0.1.0.0 (2023-05-02) Initial Release

Initial release of the module, including a setting on follow-up levels to toggle placing on credit hold. Blocks
the confirmation of sales orders for clients on credit hold. Red "Credit Hold" banner appears on sales orders and
partner form view when a client is on credit hold. Credit hold can be postponed by setting the "Postpone Hold" field
on the partner form view.