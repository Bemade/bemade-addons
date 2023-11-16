from odoo import models, fields, api


class PlanningSlot(models.Model):
    _inherit = "planning.slot"

    inbound_travel_slot = fields.Many2one(comodel_name="planning.slot",
                                          string="Inbound Travel Plan", )
    outbound_travel_slot = fields.Many2one(comodel_name="planning.slot",
                                           string="Outbound Travel Plan")

    # Fields for travel slots
    travel_origin_slot = fields.One2many(comodel_name="planning.slot",
                                         inverse_name="outbound_travel_slot")
    travel_destination_slot = fields.One2many(comodel_name="planning.slot",
                                              inverse_name="inbound_travel_slot")
    is_travel_slot = fields.Boolean()

    def action_plan_travel(self):
        # Get previous and next planning records for the same day, same resource
        for rec in self:
            prev_slot = rec._get_previous_same_day_same_resource_slot()
            next_slot = rec._get_next_same_day_same_resource_slot()


    def _get_previous_same_day_same_resource_slot(self):
        start = self.start_datetime.replace(hour=0, minute=0, second=0,
                                            microsecond=0)
        domain = [('is_travel_slot', '=', False),
                  ('start_datetime', '>=', start),
                  ('end_datetime', '<=', self.start_datetime),
                  ('resource_id', '=', self.resource_id.id)]
        return self.env['planning.slot'].search(domain)

    def _get_next_same_day_same_resource_slot(self):
        end = self.end_datetime.replace(hour=23, minute=59, second=59,
                                        microsecond=999999)
        domain = [('is_travel_slot', '=', False),
                  ('start_datetime', '>=', self.end_datetime),
                  ('end_datetime', '<=', end),
                  ('resource_id', '=', self.resource_id.id)]
        return self.env['planning.slot'].search(domain)
