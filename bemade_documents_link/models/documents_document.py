from odoo import _, api, fields, models
from odoo.exceptions import UserError


class DocumentsDocument(models.Model):
    _inherit = "documents.document"

    bemade_link_ids = fields.One2many(
        "bemade.documents.link",
        "document_id",
        string="Linked Records",
    )
    bemade_linked_record_count = fields.Integer(
        compute="_compute_bemade_linked_record_count",
        store=True,
    )

    @api.depends("bemade_link_ids")
    def _compute_bemade_linked_record_count(self):
        # Rows are unique per (document, res_model, res_id), so their count
        # is exactly the number of distinct records this document is linked
        # to across every model (task #3678 AC5).
        for document in self:
            document.bemade_linked_record_count = len(document.bemade_link_ids)

    def action_view_linked_records(self):
        self.ensure_one()
        return {
            "name": _("Linked Records"),
            "type": "ir.actions.act_window",
            "res_model": "bemade.documents.link",
            "view_mode": "list,form",
            "domain": [("document_id", "=", self.id)],
        }

    def _bemade_repoint_primary(self):
        """Called when the link row that is the current native primary
        (``res_model``/``res_id``) is removed: repoint the native primary to
        another remaining link row, or reset it to the self-referential
        ``'documents.document'`` sentinel (matching a freshly-uploaded,
        unlinked document) if none remain."""
        self.ensure_one()
        remaining = self.bemade_link_ids
        if remaining:
            primary = remaining[0]
            self.write({"res_model": primary.res_model, "res_id": primary.res_id})
        else:
            self.write({"res_model": "documents.document", "res_id": self.id})

    def action_link_to_record(self, model=False):
        """Documents-side entry point (task #3678 defect 1 / AC3): the stock
        version (enterprise/documents/models/documents_document.py) refuses
        to open the wizard at all when any selected document is already
        linked (``res_model != 'documents.document'``). Since a document can
        now be linked to many records, that refusal no longer applies --
        override it (not monkey-patch the base method) so only our subclass
        drops the guard.

        This is a full copy of the stock method minus the "already linked"
        early-return block; everything else -- context keys, the ``model``
        pre-selection branch, the returned act_window -- is unchanged.
        """
        context = {
            "default_document_ids": self.ids,
            "default_resource_ref": False,
            "default_is_readonly_model": False,
            "default_model_id": False,
        }

        if model:
            self.env[model].check_access("write")
            context["default_is_readonly_model"] = True
            context["default_model_id"] = self.env["ir.model"]._get_id(model)
            first_valid_id = self.env[model].search([], limit=1).id
            if not first_valid_id:
                raise UserError(
                    _("There are no records to link this document. Create one first.")
                )
            context["default_resource_ref"] = f"{model},{first_valid_id}"

        return {
            "name": _("Choose a record to link"),
            "type": "ir.actions.act_window",
            "res_model": "documents.link_to_record_wizard",
            "view_mode": "form",
            "target": "new",
            "views": [(False, "form")],
            "context": context,
        }

    def _bemade_sync_product_document(self):
        """Ensure a ``product.document`` exists for any of these documents that
        are linked to a product.

        The product "Documents" smart button reads the **``product.document``**
        model (filtered by ``res_model`` / ``res_id`` on the shared
        ``ir.attachment``), NOT ``documents.document``. When a file is uploaded
        from a product, the stock ``ir.attachment.create`` override creates the
        ``product.document`` for us; but when an *existing* ``documents.document``
        is merely *re-linked* to a product (the whole point of this module), only
        its ``res_model`` / ``res_id`` change — via a ``write`` that propagates to
        the attachment with ``no_document=True`` — so no ``product.document`` is
        ever created and the document never appears under the product's smart
        button (task #3678 defect 2).

        This bridges that gap: for each document now linked to a product and
        backed by a real attachment, create the matching ``product.document``
        (idempotently) so it surfaces on the product. The bridge is a soft
        dependency — it is a no-op when ``documents_product`` (which provides the
        ``product.document`` smart-button integration) is not installed.
        """
        ProductDocument = self.env.get("product.document")
        if ProductDocument is None:
            # documents_product not installed -> no product smart button to feed.
            return
        product_models = ("product.template", "product.product")
        to_bridge = self.filtered(
            lambda d: d.res_model in product_models
            and d.res_id
            and d.attachment_id
        )
        if not to_bridge:
            return
        # Only create what is missing — keep idempotent across repeated links.
        existing = self.env["product.document"].sudo().search(
            [("ir_attachment_id", "in", to_bridge.attachment_id.ids)]
        )
        existing_attachment_ids = set(existing.mapped("ir_attachment_id").ids)
        vals_list = [
            {"ir_attachment_id": doc.attachment_id.id}
            for doc in to_bridge
            if doc.attachment_id.id not in existing_attachment_ids
        ]
        if not vals_list:
            return
        # The attachment already carries res_model / res_id (propagated by
        # documents.document._inverse_res_model) AND already has its own
        # documents.document. Create the product.document with no_document=True
        # so the documents bridge does not try to create a SECOND
        # documents.document for the same attachment (which would violate the
        # documents_document_attachment_unique constraint).
        self.env["product.document"].sudo().with_context(
            no_document=True
        ).create(vals_list)
