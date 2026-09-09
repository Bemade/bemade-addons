from datetime import timedelta

from odoo import api, fields, models


class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"

    def _auto_init(self):
        # Create columns and populate them BEFORE super() so Odoo sees them as
        # existing and doesn't trigger ORM recomputation (which causes memory issues)
        cr = self.env.cr
        cr.execute(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'sale_order_line'
            AND column_name IN ('is_delivered', 'expected_ship_date')
        """
        )
        existing_cols = {r[0] for r in cr.fetchall()}

        if "is_delivered" not in existing_cols:
            cr.execute(
                """
                ALTER TABLE sale_order_line
                ADD COLUMN is_delivered boolean
            """
            )
            cr.execute(
                """
                UPDATE sale_order_line
                SET is_delivered = (qty_delivered >= product_uom_qty)
            """
            )

        if "expected_ship_date" not in existing_cols:
            cr.execute(
                """
                ALTER TABLE sale_order_line
                ADD COLUMN expected_ship_date date
            """
            )
            cr.execute(
                """
                UPDATE sale_order_line sol
                SET expected_ship_date = (
                    COALESCE(so.date_order::date, CURRENT_DATE)
                    + COALESCE(sol.customer_lead, 0) * INTERVAL '1 day'
                )::date
                FROM sale_order so
                WHERE sol.order_id = so.id
            """
            )

        return super()._auto_init()

    expected_ship_date = fields.Date(
        string="Expected Ship Date",
        compute="_compute_expected_ship_date",
        inverse="_inverse_expected_ship_date",
        store=True,
        help="Expected date when this order line will be shipped.",
    )

    is_late = fields.Boolean(
        string="Late",
        compute="_compute_is_late",
        search="_search_is_late",
    )

    is_delivered = fields.Boolean(
        string="Delivered",
        compute="_compute_is_delivered",
        store=True,
    )

    @api.depends("qty_delivered", "product_uom_qty")
    def _compute_is_delivered(self):
        for line in self:
            line.is_delivered = line.qty_delivered >= line.product_uom_qty

    @api.depends("order_id.date_order", "customer_lead")
    def _compute_expected_ship_date(self):
        for line in self:
            if line.order_id.state in ("draft", "sent"):
                base_date = fields.Date.context_today(line)
            else:
                base_date = (
                    line.order_id.date_order.date()
                    if line.order_id.date_order
                    else fields.Date.context_today(line)
                )
            if line.customer_lead:
                line.expected_ship_date = base_date + timedelta(days=line.customer_lead)
            else:
                line.expected_ship_date = base_date

    def _inverse_expected_ship_date(self):
        for line in self:
            if line.order_id.state in ("draft", "sent"):
                base_date = fields.Date.context_today(line)
            else:
                base_date = (
                    line.order_id.date_order.date()
                    if line.order_id.date_order
                    else fields.Date.context_today(line)
                )
            if line.expected_ship_date:
                delta = (line.expected_ship_date - base_date).days
                line.customer_lead = max(0, delta)

    def _search_is_late(self, operator, value):
        late_dom = [
            ("order_id.state", "=", "sale"),
            ("expected_ship_date", "<", fields.Date.today()),
            ("is_delivered", "=", False),
            ("product_id.type", "!=", "service"),
        ]
        not_late_dom = [
            ("order_id.state", "=", "sale"),
            "|",
            "|",
            ("expected_ship_date", ">=", fields.Date.today()),
            ("is_delivered", "=", True),
            ("product_id.type", "=", "service"),
        ]

        if operator == "=":
            return late_dom if value else not_late_dom
        if operator == "!=":
            return not_late_dom if value else late_dom
        if operator == "in":
            if False in value and True in value:
                return [("order_id.state", "=", "sale")]
            elif True in value:
                return late_dom
            elif False in value:
                return not_late_dom
        if operator == "not in":
            if False in value and True in value:
                return []
            elif True in value:
                return not_late_dom
            elif False in value:
                return late_dom
        return []

    @api.depends("is_delivered", "order_id.state", "expected_ship_date", "product_id")
    def _compute_is_late(self):
        today = fields.Date.today()
        for line in self:
            line.is_late = (
                not line.is_delivered
                and line.order_id.state == "sale"
                and line.expected_ship_date
                and line.expected_ship_date < today
                and line.product_id.type != "service"
            )
