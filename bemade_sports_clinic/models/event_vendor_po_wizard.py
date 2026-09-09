from odoo import api, fields, models
from odoo.exceptions import UserError


class SportsEventVendorPOWizard(models.TransientModel):
    _name = 'sports.event.vendor.po.wizard'
    _description = 'Add Timesheets to Vendor Purchase Order'

    timesheet_ids = fields.Many2many(
        'sports.event.timesheet', string='Timesheets',
        help='Selected timesheets to add to a vendor purchase order.')

    therapist_partner_id = fields.Many2one(
        'res.partner', string='Therapist (Vendor)', readonly=True,
        help='Therapist partner inferred from selected timesheets.')

    purchase_order_id = fields.Many2one(
        'purchase.order', string='Vendor Purchase Order',
        domain="[('partner_id','=',therapist_partner_id), ('state','in',['draft'])]",
        help='Choose an open (draft) vendor purchase order for the therapist.')

    create_new_if_missing = fields.Boolean(
        string='Create New Draft PO if none selected', default=True,
        help='When enabled and no PO is selected, a new draft PO will be created for the therapist.')

    # No manual line text override; descriptions will be built per timesheet/event

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_model = self.env.context.get('active_model')
        active_ids = self.env.context.get('active_ids') or []
        if active_model != 'sports.event.timesheet' or not active_ids:
            raise UserError('This action must be called from Event Timesheets list view.')

        timesheets = self.env['sports.event.timesheet'].browse(active_ids).exists()
        if not timesheets:
            raise UserError('No valid timesheets selected.')

        # Enforce a single therapist across all selected timesheets
        therapist_partners = timesheets.mapped('therapist_partner_id')
        if len(therapist_partners) != 1:
            raise UserError('Select timesheets for a single therapist only.')

        therapist = therapist_partners[0]
        res['timesheet_ids'] = [(6, 0, timesheets.ids)]
        res['therapist_partner_id'] = therapist.id

        # Prefill open PO if any
        po = self.env['purchase.order'].search([
            ('partner_id', '=', therapist.id),
            ('state', 'in', ['draft'])
        ], order='id desc', limit=1)
        if po:
            res['purchase_order_id'] = po.id
        return res

    # -----------------------------
    # Helpers
    # -----------------------------
    def _get_config_product(self, key):
        ICP = self.env['ir.config_parameter'].sudo()
        pid = int(ICP.get_param(key, default='0') or 0)
        return self.env['product.product'].browse(pid) if pid else self.env['product.product']

    def _build_line_description(self, ts):
        event = ts.event_id
        if event.date_start:
            local_start = fields.Datetime.context_timestamp(self, event.date_start)
            date_str = fields.Date.to_string(local_start.date())
        else:
            date_str = ''
        if event.event_type == 'clinic':
            name = (event.name or '')
            return f"{name}\n{date_str}"
        team = ', '.join(event.team_ids.mapped('name')) if event.team_ids else ''
        venue = (event.venue_id and event.venue_id.name) or ''
        return f"{team}\n{date_str} @ {venue}"

    def _ensure_po(self):
        self.ensure_one()
        if self.purchase_order_id:
            return self.purchase_order_id
        if not self.create_new_if_missing:
            raise UserError('Please select a Vendor Purchase Order, or enable quick create.')
        if not self.therapist_partner_id:
            raise UserError('Therapist partner not found.')
        po = self.env['purchase.order'].create({
            'partner_id': self.therapist_partner_id.id,
        })
        return po

    # -----------------------------
    # Action
    # -----------------------------
    def action_add_to_vendor_po(self):
        self.ensure_one()
        if not self.timesheet_ids:
            raise UserError('Please select at least one timesheet.')

        # Vendor-side products (required). For clinic events use clinic vendor product.
        prod_cov_vendor = self._get_config_product('bemade_sports_clinic.product_event_coverage_vendor_id')
        prod_trv_vendor = self._get_config_product('bemade_sports_clinic.product_event_travel_vendor_id')
        prod_cli_vendor = self._get_config_product('bemade_sports_clinic.product_event_clinic_vendor_id')
        if not prod_cov_vendor or not prod_cov_vendor.exists():
            raise UserError('Configure the Therapist Coverage Product (Vendor PO) in settings.')
        if not prod_trv_vendor or not prod_trv_vendor.exists():
            raise UserError('Configure the Therapist Travel Product (Vendor PO) in settings.')
        if not prod_cli_vendor or not prod_cli_vendor.exists():
            # Only strictly required when processing clinic events; check later per timesheet
            prod_cli_vendor = self.env['product.product']

        # Make or get the target PO
        po = self._ensure_po()

        # Validate therapist consistency once more
        therapist_partners = self.timesheet_ids.mapped('therapist_partner_id')
        if len(therapist_partners) != 1 or therapist_partners[0] != self.therapist_partner_id:
            raise UserError('All selected timesheets must belong to the same therapist.')

        POL = self.env['purchase.order.line']

        created_lines = 0
        for ts in self.timesheet_ids:
            desc = self._build_line_description(ts)
            is_clinic = ts.event_id and ts.event_id.event_type == 'clinic'
            # Resolve vendor price using product seller for this vendor, fallback to standard_price
            def _get_vendor_price(product, qty):
                seller = product._select_seller(partner_id=po.partner_id, quantity=qty, date=po.date_order, uom_id=product.uom_id)
                return (seller and seller.price) or product.standard_price or 0.0
            if is_clinic:
                if not prod_cli_vendor or not prod_cli_vendor.exists():
                    raise UserError('Configure the Clinic Product (Vendor PO) in settings to process clinic events.')
                # Clinics: only clinic product; disallow travel time
                if ts.travel_duration:
                    raise UserError('Clinic events cannot include travel time on vendor POs. Adjust the timesheet to remove travel time.')
                if ts.coverage_duration and not ts.purchase_coverage_line_id:
                    pol_cli = POL.create({
                        'order_id': po.id,
                        'product_id': prod_cli_vendor.id,
                        'name': desc,
                        'product_qty': ts.coverage_duration,
                        'price_unit': _get_vendor_price(prod_cli_vendor, ts.coverage_duration),
                        'product_uom': prod_cli_vendor.uom_id.id,
                    })
                    ts.write({'purchase_coverage_line_id': pol_cli.id, 'vendor_purchase_order_id': po.id})
                    created_lines += 1
            else:
                # Standard events: coverage + travel products
                if ts.coverage_duration and not ts.purchase_coverage_line_id:
                    pol_cov = POL.create({
                        'order_id': po.id,
                        'product_id': prod_cov_vendor.id,
                        'name': desc,
                        'product_qty': ts.coverage_duration,
                        'price_unit': _get_vendor_price(prod_cov_vendor, ts.coverage_duration),
                        'product_uom': prod_cov_vendor.uom_id.id,
                    })
                    ts.write({'purchase_coverage_line_id': pol_cov.id, 'vendor_purchase_order_id': po.id})
                    created_lines += 1
                if ts.travel_duration and not ts.purchase_travel_line_id:
                    pol_trv = POL.create({
                        'order_id': po.id,
                        'product_id': prod_trv_vendor.id,
                        'name': desc,
                        'product_qty': ts.travel_duration,
                        'price_unit': _get_vendor_price(prod_trv_vendor, ts.travel_duration),
                        'product_uom': prod_trv_vendor.uom_id.id,
                    })
                    ts.write({'purchase_travel_line_id': pol_trv.id, 'vendor_purchase_order_id': po.id})
                    created_lines += 1

        if created_lines == 0:
            # Provide a clear reason message to guide the user
            raise UserError('No vendor PO lines were created. Ensure the selected timesheets have non-zero coverage or travel durations and are not already linked to a vendor PO.')

        # Open the PO just used/created
        action = self.env.ref('purchase.purchase_form_action').read()[0]
        action.update({'res_id': po.id, 'view_mode': 'form', 'views': [(False, 'form')], 'target': 'current'})
        return action
