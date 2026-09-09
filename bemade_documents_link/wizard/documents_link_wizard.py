from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Command


class DocumentsLinkWizard(models.TransientModel):
    """Record-side wizard: reconcile which existing ``documents.document``
    records are linked to the record the user is currently on (resolved from
    the ``active_model`` / ``active_id`` context).

    A document can now be linked to many records (task #3678), so this is a
    checked picker rather than an "unlinked documents only" selector: it
    defaults to the documents already linked to the active record, and saving
    reconciles the selection into ``bemade.documents.link`` rows -- creating
    rows for newly-checked documents, removing rows for unchecked ones.
    """

    _name = "documents.link.wizard"
    _description = "Link Existing Documents to Record"

    res_model = fields.Char(
        string="Target Model",
        required=True,
        default=lambda self: self.env.context.get("active_model"),
    )
    res_id = fields.Integer(
        string="Target Record",
        required=True,
        default=lambda self: self.env.context.get("active_id"),
    )
    document_ids = fields.Many2many(
        "documents.document",
        string="Documents",
    )

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if "document_ids" in fields_list:
            res_model = res.get("res_model") or self.env.context.get("active_model")
            res_id = res.get("res_id") or self.env.context.get("active_id")
            if res_model and res_id:
                links = self.env["bemade.documents.link"].search(
                    [("res_model", "=", res_model), ("res_id", "=", res_id)]
                )
                res["document_ids"] = [Command.set(links.document_id.ids)]
        return res

    def action_link(self):
        self.ensure_one()

        # Gate on the user's *write* access to the target record, mirroring the
        # stock Documents link wizard's access logic, so a user cannot link a
        # document to a record they are not allowed to modify.
        target_model = self.res_model
        if target_model not in self.env or self.env[target_model]._abstract:
            raise UserError(_("Cannot link documents to model %s.", target_model))
        target = self.env[target_model].browse(self.res_id)
        if not target.exists():
            raise UserError(_("The record to link the documents to no longer exists."))
        target.check_access("write")

        Link = self.env["bemade.documents.link"]
        existing_links = Link.search(
            [("res_model", "=", target_model), ("res_id", "=", self.res_id)]
        )
        existing_docs = existing_links.document_id
        selected_docs = self.document_ids

        to_remove = existing_links.filtered(
            lambda link: link.document_id not in selected_docs
        )
        to_add = selected_docs - existing_docs

        if to_remove:
            to_remove.unlink()
        for document in to_add:
            Link.create(
                {
                    "document_id": document.id,
                    "res_model": target_model,
                    "res_id": self.res_id,
                }
            )
        if to_add:
            to_add.write({"is_editable_attachment": True})
            # Surface newly-linked docs under a product's smart button (#3678).
            to_add._bemade_sync_product_document()
        return {"type": "ir.actions.act_window_close"}
