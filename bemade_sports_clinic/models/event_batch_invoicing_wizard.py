from odoo import _, api, fields, models
from odoo.exceptions import UserError


class SportsEventBatchInvoicingWizard(models.TransientModel):
    _name = 'sports.event.batch_invoicing.wizard'
    _description = 'Batch Add Events to Sale Orders'

    event_ids = fields.Many2many('sports.event', string='Events')
    description = fields.Text(string='Description')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_ids = self.env.context.get('active_ids') or []
        if active_ids and 'event_ids' in fields_list:
            res['event_ids'] = [(6, 0, active_ids)]
        return res

    def _get_config_product(self, key):
        ICP = self.env['ir.config_parameter'].sudo()
        pid = int(ICP.get_param(key, default='0') or 0)
        return self.env['product.product'].browse(pid) if pid else self.env['product.product']

    @api.model
    def _t_therapists_label(self):
        # Uses current env.context['lang'] for translation
        return _("Therapists: %s")

    def _build_event_line_description(self, ts):
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

    def _ensure_sale_order_for_partner(self, partner, earliest_date=None):
        so = self.env['sale.order'].search([
            ('partner_id', '=', partner.id),
            ('state', '=', 'draft')
        ], order='id desc', limit=1)
        if so:
            return so
        vals = {'partner_id': partner.id}
        if earliest_date:
            vals['date_order'] = earliest_date
        return self.env['sale.order'].create(vals)

    def action_process(self):
        self.ensure_one()
        events = self.event_ids
        if not events:
            raise UserError('Select at least one event.')

        prod_cov_customer = self._get_config_product('bemade_sports_clinic.product_event_coverage_customer_id')
        prod_trv_customer = self._get_config_product('bemade_sports_clinic.product_event_travel_customer_id')
        prod_clinic_customer = self._get_config_product('bemade_sports_clinic.product_event_clinic_customer_id')
        if not prod_clinic_customer or not prod_clinic_customer.exists():
            raise UserError('Configure the Clinic Product (Customer Invoice) in settings.')
        if not prod_cov_customer or not prod_cov_customer.exists():
            raise UserError('Configure the Coverage Product (Customer Invoice) in settings.')
        if not prod_trv_customer or not prod_trv_customer.exists():
            raise UserError('Configure the Travel Product (Customer Invoice) in settings.')

        partners = {}
        for ev in events:
            if not ev.partner_id:
                raise UserError(f'Event "{ev.display_name}" is missing an organization.')
            partners.setdefault(ev.partner_id.id, []).append(ev)

        created_sos = self.env['sale.order']
        for partner_id, evs in partners.items():
            partner = self.env['res.partner'].browse(partner_id)
            earliest_date = min((e.date_start for e in evs if e.date_start), default=None)
            so = self._ensure_sale_order_for_partner(partner, earliest_date=earliest_date)
            lang = partner.lang or so.partner_id.lang or self.env.user.lang
            created_sos |= so
            for ev in evs:
                # Build a base description for this event
                base_desc = None
                # We will compute merged lines per type
                if ev.event_type == 'clinic':
                    # Merge coverage for all eligible timesheets
                    cov_ts = ev.timesheet_ids.filtered(lambda t: t.coverage_duration and not t.sale_coverage_line_id)
                    total_cov = sum(cov_ts.mapped('coverage_duration')) if cov_ts else 0.0
                    if total_cov:
                        if base_desc is None:
                            # Use any contributing timesheet to render base
                            base_desc = (self.description or '').strip() or self._build_event_line_description(cov_ts[:1])
                        therapists = ', '.join(sorted(set(cov_ts.mapped('user_id.name'))))
                        label = (self.with_context(lang=lang))._t_therapists_label()
                        name = f"{base_desc}\n{label % therapists}" if therapists else base_desc
                        sol_cli = self.env['sale.order.line'].create({
                            'order_id': so.id,
                            'product_id': prod_clinic_customer.id,
                            'name': name,
                            'product_uom_qty': total_cov,
                            'product_uom': prod_clinic_customer.uom_id.id,
                        })
                        # Link all contributing timesheets and mark invoiced
                        # Link first, then mark invoiced to respect read-only rules on invoiced timesheets
                        cov_ts.write({'sale_coverage_line_id': sol_cli.id})
                        cov_ts.write({'state': 'invoiced'})
                    # Clinics: skip travel in batch
                else:
                    # Build selections without excluding by state; we'll set state after linking both
                    cov_ts = ev.timesheet_ids.filtered(lambda t: t.coverage_duration and not t.sale_coverage_line_id)
                    total_cov = sum(cov_ts.mapped('coverage_duration')) if cov_ts else 0.0
                    if total_cov:
                        if base_desc is None:
                            base_desc = (self.description or '').strip() or self._build_event_line_description(cov_ts[:1])
                        therapists_cov = ', '.join(sorted(set(cov_ts.mapped('user_id.name'))))
                        label = (self.with_context(lang=lang))._t_therapists_label()
                        name_cov = f"{base_desc}\n{label % therapists_cov}" if therapists_cov else base_desc
                        sol_cov = self.env['sale.order.line'].create({
                            'order_id': so.id,
                            'product_id': prod_cov_customer.id,
                            'name': name_cov,
                            'product_uom_qty': total_cov,
                            'product_uom': prod_cov_customer.uom_id.id,
                        })
                        cov_ts.write({'sale_coverage_line_id': sol_cov.id})

                    # Travel
                    trv_ts = ev.timesheet_ids.filtered(lambda t: t.travel_duration and not t.sale_travel_line_id)
                    total_trv = sum(trv_ts.mapped('travel_duration')) if trv_ts else 0.0
                    if total_trv:
                        if base_desc is None:
                            # fallback if no coverage lines contributed to base_desc
                            base_desc = (self.description or '').strip() or self._build_event_line_description(trv_ts[:1])
                        therapists_trv = ', '.join(sorted(set(trv_ts.mapped('user_id.name'))))
                        label = (self.with_context(lang=lang))._t_therapists_label()
                        name_trv = f"{base_desc}\n{label % therapists_trv}" if therapists_trv else base_desc
                        sol_trv = self.env['sale.order.line'].create({
                            'order_id': so.id,
                            'product_id': prod_trv_customer.id,
                            'name': name_trv,
                            'product_uom_qty': total_trv,
                            'product_uom': prod_trv_customer.uom_id.id,
                        })
                        trv_ts.write({'sale_travel_line_id': sol_trv.id})

                    # After linking coverage/travel, mark all contributing timesheets invoiced
                    ts_to_mark = (cov_ts | trv_ts)
                    if ts_to_mark:
                        ts_to_mark.write({'state': 'invoiced'})

                # If all timesheets are invoiced for the event, update event state
                ev_ts = ev.timesheet_ids
                if ev_ts and all(t.state == 'invoiced' for t in ev_ts):
                    try:
                        ev.write({'state': 'invoiced'})
                    except Exception:
                        pass

        action = {
            'type': 'ir.actions.act_window',
            'res_model': 'sale.order',
            'view_mode': 'list,form',
            'target': 'current',
        }
        if created_sos:
            action['domain'] = [('id', 'in', created_sos.ids)]
        return action
