from odoo import _, api, fields, models
from odoo.exceptions import MissingError


class BemadeDocumentsLink(models.Model):
    """Polymorphic link between a ``documents.document`` and any business
    record (task #3678): the source of truth for "which records is this
    document linked to". A single document can be linked to many records
    across many different models -- something the stock Documents module
    can't express, since it only tracks a single ``res_model``/``res_id``
    pointer per document and refuses to (re-)link an already-linked one.

    The stock ``documents.document.res_model``/``res_id`` pair is kept as a
    synced "primary" link so the native Documents card, ``res_name``, and the
    product smart-button bridge keep working unchanged: the *first* link row
    created for a document also sets the native primary; additional rows only
    add links (they never touch the native pointer). Removing the primary row
    repoints the native pointer to another remaining link row, or resets it to
    the self-referential ``'documents.document'`` sentinel when none remain,
    mirroring how a freshly-uploaded, unlinked document looks.
    """

    _name = "bemade.documents.link"
    _description = "Document Link to Record"

    document_id = fields.Many2one(
        "documents.document",
        required=True,
        ondelete="cascade",
        index=True,
    )
    res_model = fields.Char(required=True, index=True)
    res_id = fields.Many2oneReference(
        required=True, index=True, model_field="res_model"
    )
    res_name = fields.Char(compute="_compute_res_name", compute_sudo=True)
    record_ref = fields.Reference(
        string="Record",
        selection="_selection_target_model",
        compute="_compute_record_ref",
    )

    _sql_constraints = [
        (
            "doc_record_uniq",
            "unique(document_id, res_model, res_id)",
            "A document can be linked to a record only once.",
        ),
    ]

    @api.model
    def _selection_target_model(self):
        # Mirror the stock link_to_record_wizard's target-model scope: any
        # mail.thread model other than documents.document itself.
        return [
            (model.model, model.name)
            for model in self.env["ir.model"]
            .sudo()
            .search(
                [
                    ("model", "!=", "documents.document"),
                    ("is_mail_thread", "=", "True"),
                ]
            )
        ]

    @api.depends("res_model", "res_id")
    def _compute_res_name(self):
        for link in self:
            if link.res_model and link.res_id:
                try:
                    link.res_name = (
                        self.env[link.res_model].browse(link.res_id).display_name
                    )
                except MissingError:
                    link.res_name = False
            else:
                link.res_name = False

    @api.depends("res_model", "res_id")
    def _compute_record_ref(self):
        for link in self:
            if (
                link.res_model
                and link.res_id
                and link.res_model in self.env
                and self.env[link.res_model].browse(link.res_id).exists()
            ):
                link.record_ref = f"{link.res_model},{link.res_id}"
            else:
                link.record_ref = False

    @api.model_create_multi
    def create(self, vals_list):
        links = super().create(vals_list)
        skip_audit = self.env.context.get("skip_bemade_link_audit")
        for link in links:
            link._sync_primary_on_link()
            if not skip_audit:
                link._post_chatter_audit(_("linked to"))
        return links

    def unlink(self):
        # A row that IS the current native primary needs its document
        # repointed once it's gone; figure that out (and post the chatter
        # note) BEFORE the rows disappear, then repoint after the actual
        # unlink.
        documents_to_repoint = self.env["documents.document"]
        for link in self:
            document = link.document_id
            if (
                document.res_model == link.res_model
                and document.res_id == link.res_id
            ):
                documents_to_repoint |= document
            link._post_chatter_audit(_("unlinked from"))
        result = super().unlink()
        for document in documents_to_repoint:
            document._bemade_repoint_primary()
        return result

    def _sync_primary_on_link(self):
        """The first link row on a document also becomes the native primary
        (``res_model``/``res_id``) so stock Documents UX keeps working;
        subsequent rows just add a link and leave the primary alone."""
        self.ensure_one()
        document = self.document_id
        if document.res_model == "documents.document":
            document.write({"res_model": self.res_model, "res_id": self.res_id})

    def _post_chatter_audit(self, action):
        """Post a one-line note on the *target* record's chatter (not on the
        document itself) when a link is created/removed. Degrades gracefully
        if the target model/record no longer exists or isn't a mail.thread."""
        self.ensure_one()
        if not self.res_model or self.res_model not in self.env:
            return
        target = self.env[self.res_model].browse(self.res_id)
        if not target.exists() or not hasattr(target, "message_post"):
            return
        target.message_post(
            body=_(
                "Document %(document)s was %(action)s this record.",
                document=self.document_id.name,
                action=action,
            )
        )
