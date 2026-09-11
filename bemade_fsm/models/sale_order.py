from odoo import fields, models, api, _
import ast
from odoo.osv.expression import AND


class SaleOrder(models.Model):
    _inherit = "sale.order"

    valid_equipment_ids = fields.One2many(
        comodel_name="fsm.equipment",
        related="partner_id.commercial_partner_id.owned_equipment_ids",
    )

    default_equipment_ids = fields.Many2many(
        comodel_name="fsm.equipment",
        string="Default Equipment to Service",
        help="The default equipment to service for new sale order lines.",
        compute="_compute_default_equipment",
        inverse="_inverse_default_equipment",
        store=True,
    )

    summary_equipment_ids = fields.Many2many(
        comodel_name="fsm.equipment",
        string="Equipment Being Serviced",
        compute="_compute_summary_equipment_ids",
    )

    site_contacts = fields.Many2many(
        comodel_name="res.partner",
        relation="sale_order_site_contacts_rel",
        compute="_compute_default_contacts",
        inverse="_inverse_default_contacts",
        store=True,
    )

    work_order_contacts = fields.Many2many(
        comodel_name="res.partner",
        relation="sale_order_work_order_contacts_rel",
        compute="_compute_default_contacts",
        inverse="_inverse_default_contacts",
        string="Work Order Recipients",
        store=True,
    )

    visit_ids = fields.One2many(
        comodel_name="bemade_fsm.visit", inverse_name="sale_order_id", readonly=False,
        copy=False
    )

    is_fsm = fields.Boolean(
        compute="_compute_is_fsm",
        string="Is FSM",
        store=True,
    )

    def get_relevant_order_lines(self, task_id):
        self.ensure_one()
        linked_lines = self.order_line.filtered(
            lambda line: line.task_id == task_id
            or line == task_id.visit_id.so_section_id
        )
        visit_lines = linked_lines.filtered(lambda line: line.visit_id)
        for line in visit_lines:
            linked_lines |= line.get_section_line_ids()
        return linked_lines

    @api.depends("order_line.equipment_ids")
    def _compute_summary_equipment_ids(self):
        for rec in self:
            rec.summary_equipment_ids = rec.order_line.mapped("equipment_ids")

    @api.onchange("partner_shipping_id")
    def _onchange_partner_shipping_id(self):
        res = super()._onchange_partner_shipping_id()
        self._compute_default_equipment()
        self._compute_default_contacts()
        return res

    @api.depends("partner_shipping_id")
    def _compute_default_contacts(self):
        for rec in self:
            rec.site_contacts = rec.partner_shipping_id.site_contacts
            rec.work_order_contacts = rec.partner_shipping_id.work_order_contacts

    def _inverse_default_contacts(self):
        pass

    @api.depends(
        "partner_id",
        "partner_shipping_id",
        "partner_shipping_id.equipment_ids",
        "partner_id.owned_equipment_ids",
    )
    def _compute_default_equipment(self):
        for rec in self:
            if rec.partner_shipping_id.equipment_ids:
                ids = rec.partner_shipping_id.equipment_ids
            else:
                ids = rec.partner_id.owned_equipment_ids
            rec.default_equipment_ids = ids if len(ids) < 4 else False

    def _inverse_default_equipment(self):
        pass

    def copy(self, default=None):
        original_visits = self.visit_ids
        original_lines = self.order_line.sorted("sequence")
        rec = super().copy(default)
        new_lines = rec.order_line.sorted("sequence")
        line_map = {
            orig.id: new.id
            for orig, new in zip(original_lines, new_lines)
        }
        for visit in original_visits:
            new_section_id = line_map.get(visit.so_section_id.id)
            if not new_section_id:
                continue
            visit.copy({
                "so_section_id": new_section_id,
                "sale_order_id": rec.id,
            })
        return rec

    def _create_default_visit(self):
        """Called when an order is confirmed with lines that will create an FSM task,
        in order to make sure there is a visit line grouping all the service being done.
        """
        self.ensure_one()
        visit = self.env["bemade_fsm.visit"].create(
            {
                "label": _("Service Visit"),
                "sale_order_id": self.id,
            }
        )
        # Make sure it goes to the top of the list
        visit.so_section_id.sequence = 0

    def _create_or_organize_visits_if_needed(self):
        """Adds a visit line to the top of the order if there are not already visit
        lines for an order with lines that will create an FSM task."""
        for order in self.filtered("company_id.create_default_fsm_visit"):
            if not order.visit_ids and order.is_fsm:
                order._create_default_visit()
            if order.is_fsm:
                # Make sure that all the lines producing FSM tasks are under a visit
                visit_line_ids = (
                    order.mapped("visit_ids")
                    .mapped("so_section_id")
                    .mapped("section_line_ids")
                )
                if any(
                    [
                        True
                        for line in order.order_line.filtered(
                            lambda line: not line.display_type
                        )
                        if line not in visit_line_ids
                    ]
                ):
                    # If not, promote the first visit to the top of the order items list
                    for line in order.order_line:
                        line.sequence += 1
                    order.mapped("visit_ids").mapped("so_section_id")[0].sequence = 0

    @api.depends("order_line.is_fsm")
    def _compute_is_fsm(self):
        for rec in self:
            rec.is_fsm = any([line.is_fsm for line in rec.order_line])

    def action_confirm(self):
        self._create_or_organize_visits_if_needed()
        return super().action_confirm()

    def write(self, vals):
        res = super().write(vals)
        if "partner_shipping_id" in vals:
            for rec in self:
                rec.tasks_ids.write({"partner_id": rec.partner_shipping_id.id})
        return res

    def _tasks_ids_domain(self):
        base = super()._tasks_ids_domain()
        fsm_parent = AND([base, [('project_id.is_fsm', '=', True), ('parent_id', '=', False)]])
        non_fsm_all = AND([base, [('project_id.is_fsm', '=', False)]])
        return ['|'] + fsm_parent + non_fsm_all

    def action_view_project_ids(self):
        """Constrain the "Tasks" smart button to this order's tasks.

        Odoo 19.0 replaced sale.order.action_view_task() by
        action_view_project_ids(): for an order with a single project it opens
        that project's task action with only a removable search facet on the
        sale order, so the user lands on every task of the project (for FSM
        orders: the whole Field Service project) as soon as the facet is
        dropped or does not apply. Restore the 18.0 contract: a hard domain
        limited to the tasks of this order — top-level visit tasks only for
        FSM orders, every task otherwise (see _tasks_ids_domain).
        """
        self.ensure_one()
        action = super().action_view_project_ids()
        res_model = action.get("res_model")
        if res_model and res_model != "project.task":
            # Several projects: the native action lists projects, keep it.
            return action
        domain = self._tasks_ids_domain()
        if "has_template_ancestor" in self.env["project.task"]._fields:
            domain = AND([domain, [("has_template_ancestor", "=", False)]])
        action["domain"] = domain
        return action
        if action.get("res_model") is None and "project.task" not in str(action.get("xml_id", "")) and "task" not in str(action.get("xml_id", "")):
            return action
        own_tasks = self._tasks_ids_domain()
        existing = action.get("domain")
        if existing:
            try:
                parsed = ast.literal_eval(existing) if isinstance(existing, str) else existing
            except Exception:
                parsed = None
            if isinstance(parsed, (list, tuple)):
                # Native domain references active_id: resolve it before merging.
                parsed = [
                    (t[0], t[1], self.project_ids.id) if isinstance(t, tuple) and len(t) == 3 and t[2] == "active_id" else t
                    for t in parsed
                ]
                action["domain"] = AND([list(parsed), own_tasks])
            else:
                action["domain"] = own_tasks
        else:
            action["domain"] = own_tasks
        return action
