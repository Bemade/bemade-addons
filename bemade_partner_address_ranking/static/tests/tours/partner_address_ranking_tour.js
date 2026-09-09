// Copyright (C) 2024 Bemade Inc. (<https://www.bemade.org>).
// License LGPL-3 or later (http://www.gnu.org/licenses/lgpl).
/**
 * Tour: partner_address_ranking_tour
 *
 * Exercises the SO form's partner_invoice_id and partner_shipping_id Many2one
 * dropdowns end-to-end, asserting that:
 *  - The favorite invoice contact (C_inv2) is first in the invoice dropdown.
 *  - The most-used delivery contact (C_ship1) is first in the delivery dropdown.
 *
 * Data is seeded by TestFormWidgetTour.setUpClass in test_form_widget_tour.py.
 * The company name "TourCo", contact names "TourInv2 (fav)", and "TourShip1"
 * are expected to be pre-created by that Python setUp.
 */
import { registry } from "@web/core/registry";

registry.category("web_tour.tours").add("partner_address_ranking_tour", {
    url: "/odoo/sales",
    steps: () => [
        // ----------------------------------------------------------------
        // Step 1: Go to the Sales app and create a new quotation
        // ----------------------------------------------------------------
        {
            content: "Wait for the Sales quotation list to load",
            trigger: ".o_sale_order",
        },
        {
            content: "Click New to create a new quotation",
            trigger: "button.o_list_button_add",
            run: "click",
        },
        {
            content: "Wait for the new SO form to load",
            trigger: ".o_form_view .o_field_widget[name='partner_id'] input",
        },
        // ----------------------------------------------------------------
        // Step 2: Fill in Customer = TourCo
        // ----------------------------------------------------------------
        {
            content: "Type 'TourCo' in the Customer field",
            trigger: ".o_field_widget[name='partner_id'] input",
            run: "edit TourCo",
        },
        {
            content: "Select TourCo from the autocomplete dropdown",
            trigger: "ul.ui-autocomplete > li > a:contains('TourCo')",
            run: "click",
        },
        {
            content: "Wait for partner_invoice_id field to be populated (onchange settled)",
            trigger: ".o_field_widget[name='partner_invoice_id'] input",
        },
        // ----------------------------------------------------------------
        // Step 3: Open partner_invoice_id dropdown and assert favorite is first
        // ----------------------------------------------------------------
        {
            content: "Clear the invoice address field and open its dropdown",
            trigger: ".o_field_widget[name='partner_invoice_id'] input",
            run: "edit ",
        },
        {
            content: "Assert TourInv2 (fav) is the first invoice address option",
            trigger: "ul.ui-autocomplete > li:first-child a:contains('TourInv2')",
        },
        {
            content: "Select TourInv2 (fav) as the invoice address",
            trigger: "ul.ui-autocomplete > li:first-child a:contains('TourInv2')",
            run: "click",
        },
        // ----------------------------------------------------------------
        // Step 4: Open partner_shipping_id dropdown and assert top-ranked is first
        // ----------------------------------------------------------------
        {
            content: "Clear the shipping address field and open its dropdown",
            trigger: ".o_field_widget[name='partner_shipping_id'] input",
            run: "edit ",
        },
        {
            content: "Assert TourShip1 is the first delivery address option (highest usage)",
            trigger: "ul.ui-autocomplete > li:first-child a:contains('TourShip1')",
        },
        {
            content: "Select TourShip1 as the shipping address",
            trigger: "ul.ui-autocomplete > li:first-child a:contains('TourShip1')",
            run: "click",
        },
        // ----------------------------------------------------------------
        // Step 5: Save the SO
        // ----------------------------------------------------------------
        // Close the address autocomplete before saving. Leaving it open lets
        // the dropdown fire another name_search while the save is in flight,
        // which re-dirties the form and leaves it in edition mode at teardown.
        {
            content: "Close the address autocomplete dropdown",
            trigger: ".o_field_widget[name='partner_shipping_id'] input",
            run: "press Escape",
        },
        {
            content: "Save the quotation by clicking the Save button",
            trigger: ".o_form_button_save",
            run: "click",
        },
        {
            content: "Confirm the SO was saved (record clean, not new)",
            // NOT ":not(.o_form_editable)" — since Odoo 17 a form view is
            // always editable, so that selector only ever matches during a
            // transient re-render, letting the tour end while the save is
            // still in flight. o_form_saved is set when the record is neither
            // dirty nor new, which is the actual "saved" signal.
            trigger: ".o_form_renderer.o_form_saved",
        },
    ],
});
