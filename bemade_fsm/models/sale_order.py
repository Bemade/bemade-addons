from odoo import fields, models, api, _, Command
from odoo.exceptions import ValidationError
from odoo.tools import float_round
import re


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    valid_equipment_ids = fields.One2many(
        comodel_name="bemade_fsm.equipment",
        related="partner_id.owned_equipment_ids"
    )

    default_equipment_ids = fields.Many2many(
        comodel_name="bemade_fsm.equipment",
        string="Default Equipment to Service",
        help="The default equipment to service for new sale order lines.",
        compute="_compute_default_equipment",
        inverse="_inverse_default_equipment",
        store=True
    )

    summary_equipment_ids = fields.Many2many(
        comodel_name="bemade_fsm.equipment",
        string="Equipment Being Serviced",
        compute="_compute_summary_equipment_ids")

    site_contacts = fields.Many2many(
        comodel_name='res.partner',
        relation="sale_order_site_contacts_rel",
        compute="_compute_default_contacts",
        inverse="_inverse_default_contacts",
        string='Site Contacts',
        store=True
    )

    work_order_contacts = fields.Many2many(
        comodel_name='res.partner',
        relation='sale_order_work_order_contacts_rel',
        compute='_compute_default_contacts',
        inverse='_inverse_default_contacts',
        string='Work Order Recipients',
        store=True
    )

    visit_ids = fields.One2many(
        comodel_name='bemade_fsm.visit',
        inverse_name="sale_order_id",
        readonly=False
    )

    is_fsm = fields.Boolean(
        compute='_compute_is_fsm',
        string='Is FSM',
        store=True,
    )

    @api.depends('order_line.task_id')
    def get_relevant_order_lines(self, task_id):
        self.ensure_one()
        linked_lines = self.order_line.filtered(lambda l: l.task_id == task_id
                                                          or l == task_id.visit_id.so_section_id)
        visit_lines = linked_lines.filtered(lambda l: l.visit_id)
        for line in visit_lines:
            linked_lines |= line.get_section_line_ids()
        return linked_lines

    @api.depends('order_line.equipment_ids')
    def _compute_summary_equipment_ids(self):
        for rec in self:
            rec.summary_equipment_ids = rec.order_line.mapped('equipment_ids')

    @api.onchange('partner_shipping_id')
    def _onchange_partner_shipping_id(self):
        super()._onchange_partner_shipping_id()
        self._compute_default_equipment()
        self._compute_default_contacts()

    @api.depends('partner_shipping_id')
    def _compute_default_contacts(self):
        for rec in self:
            rec.site_contacts = rec.partner_shipping_id.site_contacts
            rec.work_order_contacts = rec.partner_shipping_id.work_order_contacts

    def _inverse_default_contacts(self):
        pass

    @api.depends(
        'partner_id',
        'partner_shipping_id',
        'partner_shipping_id.equipment_ids',
        'partner_id.owned_equipment_ids'
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
        rec = super().copy(default)
        rec.visit_ids = [Command.set(rec.order_line.visit_ids.ids)]
        return rec

    def _create_default_visit(self):
        """ Called when an order is confirmed with lines that will create an FSM task, in order to make sure there is
        a visit line grouping all the service being done."""
        self.ensure_one()
        visit = self.env['bemade_fsm.visit'].create({
            'label': _('Service Visit'),
            'sale_order_id': self.id,
        })
        # Make sure it goes to the top of the list
        visit.so_section_id.sequence = 0

    def _create_or_organize_visits_if_needed(self):
        """ Adds a visit line to the top of the order if there are not already visit lines for an order with lines that
        will create an FSM task."""
        for order in self:
            if not order.visit_ids and order.is_fsm:
                order._create_default_visit()
            if order.is_fsm:
                # Make sure that all the lines producing FSM tasks are under a visit
                visit_line_ids = order.mapped('visit_ids').mapped('so_section_id').mapped('section_line_ids')
                if any([
                    True for line in
                    order.order_line.filtered(lambda line: not line.display_type)
                    if line not in visit_line_ids
                    ]):
                    # If not, promote the first visit to the top of the order items list
                    for line in order.order_line:
                        line.sequence += 1
                    order.mapped('visit_ids').mapped('so_section_id')[0].sequence = 0

    @api.depends('order_line.is_fsm')
    def _compute_is_fsm(self):
        for rec in self:
            rec.is_fsm = any([line.is_fsm for line in rec.order_line])

    def action_confirm(self):
        self._create_or_organize_visits_if_needed()
        return super().action_confirm()
