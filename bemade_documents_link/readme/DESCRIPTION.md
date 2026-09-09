Adds two generic, reusable entry points for linking an **existing** document
(including a spreadsheet) to one or more business records, without uploading
a new file:

* **From the record side** -- a *Link existing document* item appears in the
  cog menu of every `mail.thread` form view. It opens a checked-picker
  wizard defaulting to the documents already linked to the current record;
  saving reconciles the selection (adds newly-checked documents, unlinks
  unchecked ones).
* **From the Documents side** -- a generic *Link to Record* item is added to
  the Documents app's "Action" dropdown (the enterprise Documents app renders
  a bespoke action dropdown, not the standard `ActionMenus`, so a
  `binding_model_id` server action does not surface there). It lets the user
  first choose the target model (limited to `mail.thread` models) and then
  the record, reusing the stock Documents `link_to_record_wizard` --
  repeatedly, without relaunching, and even for documents already linked
  elsewhere.

A document can be linked to **any number of records across any number of
models** (a plain M2M can't express this, since Odoo M2M targets a single
comodel): a new polymorphic `bemade.documents.link` model is the source of
truth for these links, exposed on `documents.document` as a linked-records
count and list. The stock `res_model`/`res_id` pointer is kept in sync as a
"primary" link so the native Documents card, `res_name`, and the product
smart-button bridge keep working unchanged. When the target is a product, a
matching `product.document` is also created so the linked file appears under
the product's *Documents* smart button (which reads `product.document`, not
`documents.document`).
