from odoo import _, models


class LinkToRecordWizard(models.TransientModel):
    _inherit = "documents.link_to_record_wizard"

    def link_to(self):
        """Extend the stock Documents-side link wizard (task #3678):

        * Create a ``bemade.documents.link`` row per document instead of
          overwriting the document's single native ``res_model``/``res_id``
          pointer -- so a document already linked to other records keeps
          those links (the native primary is synced automatically by
          ``bemade.documents.link.create()``'s first-link rule).
        * Bridge the product "Documents" smart button (pre-existing #3678
          defect 2 fix), unchanged.
        * Return an action re-opening this same wizard on the same documents
          (AC3: "repeat without relaunching") instead of just closing, so the
          user can link the selection to another record right away.
        """
        self.ensure_one()
        target_model = self.resource_ref._name
        target_id = self.resource_ref.id

        Link = self.env["bemade.documents.link"]
        documents = self.document_ids.with_company(self.env.company)
        already_linked = Link.search(
            [
                ("document_id", "in", documents.ids),
                ("res_model", "=", target_model),
                ("res_id", "=", target_id),
            ]
        ).document_id
        to_link = documents - already_linked
        for document in to_link:
            Link.create(
                {
                    "document_id": document.id,
                    "res_model": target_model,
                    "res_id": target_id,
                }
            )
        documents.write({"is_editable_attachment": True})
        documents._bemade_sync_product_document()

        return {
            "name": _("Choose a record to link"),
            "type": "ir.actions.act_window",
            "res_model": "documents.link_to_record_wizard",
            "view_mode": "form",
            "target": "new",
            "views": [(False, "form")],
            "context": {
                "default_document_ids": documents.ids,
                "default_resource_ref": False,
                "default_is_readonly_model": self.is_readonly_model,
                "default_model_id": self.model_id.id if self.is_readonly_model else False,
            },
        }
