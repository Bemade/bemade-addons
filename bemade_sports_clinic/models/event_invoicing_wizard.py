from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class SportsEventInvoicingWizard(models.TransientModel):
    _name = 'sports.event.invoicing.wizard'
    _description = 'Sports Event Invoicing Wizard'

    event_id = fields.Many2one('sports.event', string='Event', required=True)
    partner_id = fields.Many2one(
        'res.partner', string='Organization', related='event_id.partner_id', readonly=True)
    timesheet_ids = fields.One2many(
        related='event_id.timesheet_ids', string='Timesheets to Invoice', readonly=False,
        help='Event timesheets included in this invoicing run. Editable inline.')

    # Planned times (read-only, for visual check)
    event_date_start = fields.Datetime(
        string='Planned Event Start', related='event_id.date_start', readonly=True)
    event_date_end = fields.Datetime(
        string='Planned Event End', related='event_id.date_end', readonly=True)
    therapist_start = fields.Datetime(
        string='Planned Therapist Start', related='event_id.therapist_start', readonly=True)
    therapist_end = fields.Datetime(
        string='Planned Therapist End', related='event_id.therapist_end', readonly=True)

    # Planned duration totals (read-only)
    duration = fields.Float(
        string='Planned Event Duration', related='event_id.duration', readonly=True)
    therapist_duration = fields.Float(
        string='Planned Therapist Duration', related='event_id.therapist_duration', readonly=True)

    description = fields.Text(string='Description')

    @api.model
    def _t_therapists_label(self):
        # Uses current env.context['lang'] for translation
        return _("Therapists: %s")

    # Global customer quotation (sale order) selector
    customer_sale_order_id = fields.Many2one(
        'sale.order', string='Customer Quotation',
        domain="[('partner_id','=', partner_id), ('state','=','draft')]",
        help='Draft customer quotation to which coverage/travel lines will be added.')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_id = self.env.context.get('active_id')
        if active_id and 'event_id' in fields_list:
            res['event_id'] = active_id
        # timesheet_ids derives from event_id via One2many; no need to pre-populate
        # Default global customer quotation (draft) for event organization
        if active_id and 'customer_sale_order_id' in fields_list:
            event = self.env['sports.event'].browse(active_id)
            if event.partner_id:
                so = self.env['sale.order'].search([
                    ('partner_id', '=', event.partner_id.id),
                    ('state', '=', 'draft'),
                ], order='id desc', limit=1)
                if so:
                    res['customer_sale_order_id'] = so.id
        # Prefill description with base event info only (no therapists here)
        if active_id and 'description' in fields_list:
            event = self.env['sports.event'].browse(active_id)
            base_desc = self._build_event_description(event)
            res['description'] = base_desc
        return res

    # -----------------------------
    # Helpers
    # -----------------------------
    def _get_config_product(self, key):
        ICP = self.env['ir.config_parameter'].sudo()
        pid = int(ICP.get_param(key, default='0') or 0)
        return self.env['product.product'].browse(pid) if pid else self.env['product.product']

    def _build_event_description(self, event):
        if event.date_start:
            local_start = fields.Datetime.context_timestamp(self, event.date_start)
            date_str = fields.Date.to_string(local_start.date())
        else:
            date_str = ''
        if event.event_type == 'clinic':
            name = event.name or ''
            return f"{name}\n{date_str}"
        team_names = ', '.join(event.team_ids.mapped('name')) if event.team_ids else ''
        venue = (event.venue_id and event.venue_id.name) or ''
        return f"{team_names}\n{date_str} @ {venue}"

    def _find_vendor_po(self, vendor_partner):
        return self.env['purchase.order'].search([
            ('partner_id', '=', vendor_partner.id),
            ('state', 'in', ['draft', 'sent'])
        ], order='id desc', limit=1)

    def _build_line_description(self, ts):
        event = ts.event_id
        if event.date_start:
            local_start = fields.Datetime.context_timestamp(self, event.date_start)
            date_str = fields.Date.to_string(local_start.date())
        else:
            date_str = ''
        if event.event_type == 'clinic':
            name = event.name or ''
            return f"{name}\n{date_str}"
        team = ', '.join(event.team_ids.mapped('name')) if event.team_ids else ''
        venue = event.venue_id.name or ''
        return f"{team}\n{date_str} @ {venue}"

    # -----------------------------
    # Main action
    # -----------------------------
    def action_process(self):
        self.ensure_one()
        if not self.timesheet_ids:
            raise UserError('Please select at least one timesheet to invoice.')

        # Event type specific product policy
        is_clinic = self.event_id and self.event_id.event_type == 'clinic'

        if is_clinic:
            prod_clinic_customer = self._get_config_product('bemade_sports_clinic.product_event_clinic_customer_id')
            if not prod_clinic_customer or not prod_clinic_customer.exists():
                raise UserError('Configure the Clinic Product (Customer Invoice) in settings.')
        else:
            # Configured products (customer side only)
            prod_cov_customer = self._get_config_product('bemade_sports_clinic.product_event_coverage_customer_id')
            prod_trv_customer = self._get_config_product('bemade_sports_clinic.product_event_travel_customer_id')
            # Validate presence
            if not prod_cov_customer or not prod_cov_customer.exists():
                raise UserError('Configure the Coverage Product (Customer Invoice) in settings.')
            if not prod_trv_customer or not prod_trv_customer.exists():
                raise UserError('Configure the Travel Product (Customer Invoice) in settings.')

        # Target customer quotation (sale order)
        customer = self.event_id.partner_id
        if not customer:
            raise UserError('Event organization is required to create a quotation.')
        sale_order = self.customer_sale_order_id or self.env['sale.order'].search([
            ('partner_id', '=', customer.id),
            ('state', '=', 'draft')
        ], order='id desc', limit=1)
        if not sale_order:
            sale_order = self.env['sale.order'].create({
                'partner_id': customer.id,
                'date_order': self.event_id.date_start,
            })
        # Merge per event like batch: single SOL per type
        created_lines = 0
        POL = self.env['sale.order.line']
        # Base description and language
        base_desc = (self.description or '').strip() or self._build_event_description(self.event_id)
        lang = (sale_order.partner_id and sale_order.partner_id.lang) or self.env.user.lang

        if is_clinic:
            # No travel allowed for clinics
            if any(self.timesheet_ids.mapped('travel_duration')):
                raise UserError('Clinic events cannot include travel time on customer quotations. Adjust the timesheets to remove travel time.')
            cov_ts = self.timesheet_ids.filtered(lambda t: t.coverage_duration and not t.sale_coverage_line_id)
            total_cov = sum(cov_ts.mapped('coverage_duration')) if cov_ts else 0.0
            if total_cov:
                therapists = ', '.join(sorted(set(cov_ts.mapped('user_id.name'))))
                label = (self.with_context(lang=lang))._t_therapists_label()
                name = f"{base_desc}\n{label % therapists}" if therapists else base_desc
                sol_cli = POL.create({
                    'order_id': sale_order.id,
                    'product_id': prod_clinic_customer.id,
                    'name': name,
                    'product_uom_qty': total_cov,
                    'product_uom': prod_clinic_customer.uom_id.id,
                })
                cov_ts.write({'sale_coverage_line_id': sol_cli.id})
                created_lines += 1
        else:
            # Standard events: aggregate coverage and travel separately
            cov_ts = self.timesheet_ids.filtered(lambda t: t.coverage_duration and not t.sale_coverage_line_id)
            trv_ts = self.timesheet_ids.filtered(lambda t: t.travel_duration and not t.sale_travel_line_id)

            total_cov = sum(cov_ts.mapped('coverage_duration')) if cov_ts else 0.0
            total_trv = sum(trv_ts.mapped('travel_duration')) if trv_ts else 0.0

            if total_cov:
                therapists_cov = ', '.join(sorted(set(cov_ts.mapped('user_id.name'))))
                label_cov = (self.with_context(lang=lang))._t_therapists_label()
                name_cov = f"{base_desc}\n{label_cov % therapists_cov}" if therapists_cov else base_desc
                sol_cov = POL.create({
                    'order_id': sale_order.id,
                    'product_id': prod_cov_customer.id,
                    'name': name_cov,
                    'product_uom_qty': total_cov,
                    'product_uom': prod_cov_customer.uom_id.id,
                })
                cov_ts.write({'sale_coverage_line_id': sol_cov.id})
                created_lines += 1

            if total_trv:
                therapists_trv = ', '.join(sorted(set(trv_ts.mapped('user_id.name'))))
                label_trv = (self.with_context(lang=lang))._t_therapists_label()
                name_trv = f"{base_desc}\n{label_trv % therapists_trv}" if therapists_trv else base_desc
                sol_trv = POL.create({
                    'order_id': sale_order.id,
                    'product_id': prod_trv_customer.id,
                    'name': name_trv,
                    'product_uom_qty': total_trv,
                    'product_uom': prod_trv_customer.uom_id.id,
                })
                trv_ts.write({'sale_travel_line_id': sol_trv.id})
                created_lines += 1

        # Mark all contributing timesheets as invoiced (after linking)
        contributing = self.timesheet_ids.filtered(lambda t: t.sale_coverage_line_id or t.sale_travel_line_id)
        if contributing:
            contributing.write({'state': 'invoiced'})

        if created_lines == 0:
            raise UserError('No sale order lines were created. Ensure timesheets have non-zero durations and are not already linked to a sale order.')

        # If all event timesheets are invoiced, mark event as invoiced
        event_ts = self.event_id.timesheet_ids
        if event_ts and all(t.state == 'invoiced' for t in event_ts):
            try:
                self.event_id.write({'state': 'invoiced'})
            except Exception:
                pass
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'sports.event',
            'view_mode': 'form',
            'res_id': self.event_id.id,
            'target': 'current',
        }
