from odoo import models, fields, api
from markupsafe import Markup


class SaleOrderDuplicationWizard(models.TransientModel):
    _name = "sale.order.duplication.wizard"
    _description = "Wizard for duplicating a sale order"

    original_order_id = fields.Many2one(
        "sale.order", string="Original Order", required=True
    )
    new_quot = fields.Char(
        string="New Quotation Name", compute="_compute_new_quot", store=True
    )

    duplicate_all_lines = fields.Boolean(string="Duplicate All Lines?", default=True)
    lines_to_duplicate = fields.One2many(
        "sale.order.line.duplication.wizard",
        "wizard_id",
        string="Lines to Duplicate",
        context={"default_original_order_id": original_order_id},
    )

    purpose = fields.Text(string="Purpose")
    note = fields.Html(string="Note")

    @api.model
    def default_get(self, fields_list):
        res = super(SaleOrderDuplicationWizard, self).default_get(fields_list)
        if "default_original_order_id" in self.env.context:
            original_order_id = self.env.context["default_original_order_id"]
            original_order = self.env["sale.order"].browse(original_order_id)
            lines_vals = []
            for line in original_order.order_line:
                lines_vals.append((0, 0, {"sale_order_line_id": line.id}))
            update = {"lines_to_duplicate": lines_vals}
            if "purpose" in fields_list and "purpose" in original_order._fields:
                update["purpose"] = original_order.purpose
            if "note" in fields_list:
                update["note"] = original_order.note
            res.update(update)
        return res

    def action_duplicate_order(self):
        self.ensure_one()
        # Duplication de la commande de vente
        copy_defaults = {"note": self.note, "name": self.new_quot}
        if "purpose" in self.original_order_id._fields:
            copy_defaults["purpose"] = self.purpose
        new_order = self.original_order_id.copy(copy_defaults)
        if not self.duplicate_all_lines:
            selected_originals = self.lines_to_duplicate.filtered(
                "to_duplicate"
            ).mapped("sale_order_line_id")
            original_lines = self.original_order_id.order_line.sorted("sequence")
            new_lines = new_order.order_line.sorted("sequence")
            lines_to_remove = self.env["sale.order.line"]
            for orig, new in zip(original_lines, new_lines):
                if orig not in selected_originals:
                    lines_to_remove |= new
            lines_to_remove.unlink()

        # Préparation et envoi des messages de notification dans le chatter
        user_name = self.env.user.name
        now = fields.Datetime.now()

        # Message pour la commande originale
        original_msg_body = Markup(
            "A new quotation <a href='#' data-oe-model='sale.order' "
            "data-oe-id='%s'>#%s</a> "
            "created by %s duplicating this Quotation."
        ) % (new_order.id, new_order.name, user_name)
        self.original_order_id.message_post(body=original_msg_body)

        # Message pour la nouvelle commande dupliquée
        new_msg_body = Markup(
            "This quotation has been created by %s duplicating the original "
            "Quotation <a href='#' data-oe-model='sale.order' "
            "data-oe-id='%s'>#%s</a>."
        ) % (user_name, self.original_order_id.id, self.original_order_id.name)
        new_order.message_post(body=new_msg_body)

        return {
            "type": "ir.actions.act_window",
            "name": "Duplicated Order",
            "res_model": "sale.order",
            "res_id": new_order.id,
            "view_mode": "form",
            "target": "current",
        }

    @api.depends("original_order_id")
    def _compute_new_quot(self):
        for rec in self:
            if not rec.original_order_id:
                rec.new_quot = ""
                continue
                
            original_order_name = (
                rec.original_order_id.name.split("-")[0]
                if "-" in rec.original_order_id.name
                else rec.original_order_id.name
            )
            
            # Recherche plus précise pour éviter les doublons
            existing_quotes = self.env["sale.order"].search([
                ("name", "=like", original_order_name + "-REV%")
            ])
            
            # Trouver le prochain numéro de révision disponible
            revision_numbers = []
            for quote in existing_quotes:
                try:
                    rev_part = quote.name.split("-REV")[-1]
                    if rev_part.isdigit():
                        revision_numbers.append(int(rev_part))
                except (IndexError, ValueError):
                    continue
            
            next_revision = max(revision_numbers, default=0) + 1
            rec.new_quot = f"{original_order_name}-REV{next_revision}"
