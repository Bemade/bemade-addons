# Lost Messages Routing - UX Improvements

Enhanced user experience for managing lost messages in Odoo.

## Features

### Subcategories

Classify lost messages by type:

- **Spam / Advertising** - Unsolicited commercial emails
- **Bounce / DSN** - Delivery status notifications
- **Auto-Reply** - Out of office, vacation replies
- **Legitimate Reply** - Valid replies needing routing
- **New Inquiry** - New business inquiries
- **Finance** - Invoices, payments, accounting
- **Supplier / Vendor** - Messages from suppliers

### Batch Actions

- **Categorize** - Assign subcategory to multiple messages
- **Delete** - Remove multiple messages with confirmation
- **Finance Triage** - Process finance messages in bulk

### Triage Wizards

1. **Invalid Address Notification**

   - Notify senders they contacted wrong address
   - Detects no-reply addresses automatically
   - Customizable reply template

2. **Finance Triage**

   - Create Helpdesk ticket (if helpdesk installed)
   - Forward to finance email address

3. **Forward**
   - Real outbound "Fwd:" email sent through the configured transport
   - Correct, non-spoofed From (an authorized team address), Reply-To (the shared inbox,
     so replies re-enter triage) and References/In-Reply-To threading headers
   - Distinct from Assign/Reassign, which stays a silent internal routing with no
     outbound mail

### Search & Filters

- Filter by subcategory
- Filter uncategorized messages
- Group by subcategory

## Installation

1. Requires `mail_manual_routing_fix`
2. Install this module
3. Update database

## Optional Dependencies

- `helpdesk` - Enables creating tickets from finance triage wizard

## License

LGPL-3

## Author

Bemade Inc.
