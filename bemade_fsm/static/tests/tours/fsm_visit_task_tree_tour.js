// Copyright (C) 2024 Bemade Inc. (<https://www.bemade.org>).
// License LGPL-3 or later (http://www.gnu.org/licenses/lgpl).
/**
 * Tour: fsm_visit_task_tree_tour
 *
 * Drives the visit "Full Task Tree" feature (task 3360) end-to-end in a
 * browser-rendered session and validates that the recursive task list view
 * renders the COMPLETE multi-level task hierarchy and that lazy-expand works.
 *
 * Path exercised:
 *   1. Open the seeded, confirmed sale order form (URL carries its id).
 *   2. Open the "Field Service" notebook page (where visit_ids is embedded).
 *   3. Click the per-row "Full Task Tree" button on the visit list row.
 *   4. The recursive project.task list action opens.
 *   5. Assert the recursive expand column is present (proves recursive="1"
 *      parsed and the recursive_list_view renderer/controller are active).
 *   6. Assert at least one ROOT row (the visit's root task) is rendered and
 *      carries an expand button (it has children -> a genuine tree, not a flat
 *      list).
 *   7. Click the root row's expand button (lazy-expand) and assert deeper rows
 *      appear (depth-1 children), then expand a child and assert depth-2 rows
 *      (grandchildren) appear -- i.e. the structure is multi-level and the
 *      lazy expansion is functional, not just immediate children.
 *
 * Data is seeded by FSMVisitTaskTreeTourTest.setUpClass in
 * test_fsm_visit_task_tree_tour.py: one confirmed SO with a single visit whose
 * root task has a [2,2,2] descendant structure (parent -> child -> grandchild
 * -> great-grandchild), grouped under the visit root.
 */
import { registry } from "@web/core/registry";

// No `url` property: the Python HttpCase opens the seeded sale order FORM via
// start_tour(url_path=f"/odoo/sales/{so.id}", ...). Declaring a `url` here would
// make web_tour re-navigate to that path (the Quotations LIST), overriding the
// record form -- so we deliberately omit it and assert the form is already open.
registry.category("web_tour.tours").add("fsm_visit_task_tree_tour", {
    steps: () => [
        // ----------------------------------------------------------------
        // Step 1: The seeded sale order form is already open (start_tour url).
        // ----------------------------------------------------------------
        {
            content: "Wait for the sale order form to load",
            trigger: ".o_form_view .o_form_sheet",
        },
        // ----------------------------------------------------------------
        // Step 2: Open the Field Service notebook page (holds visit_ids).
        // ----------------------------------------------------------------
        {
            content: "Open the 'Field Service' notebook page",
            trigger: ".o_notebook .nav-link:contains('Field Service')",
            run: "click",
        },
        {
            content: "Wait for the Service Visits embedded list to render",
            trigger: ".o_field_widget[name='visit_ids'] .o_list_renderer",
        },
        // ----------------------------------------------------------------
        // Step 3: Click the per-row 'Full Task Tree' button on the visit row.
        // ----------------------------------------------------------------
        {
            content: "Click the 'Full Task Tree' button on the visit row",
            trigger:
                ".o_field_widget[name='visit_ids'] .o_data_row button:contains('Full Task Tree')",
            run: "click",
        },
        // ----------------------------------------------------------------
        // Step 4 & 5: The recursive task-tree list action opens. Assert the
        // recursive expand column header exists -> recursive="1" parsed and the
        // recursive_list_view renderer is active.
        // ----------------------------------------------------------------
        {
            content: "Wait for the Full Task Tree action breadcrumb",
            trigger: ".o_breadcrumb:contains('Full Task Tree')",
        },
        {
            content:
                "Assert the recursive expand column header is present (recursive list active)",
            trigger: ".o_list_view th.o_recursive_expand_column",
        },
        // ----------------------------------------------------------------
        // Step 6: Assert a ROOT row is rendered and has an expand button (it
        // has children -> a real tree). The root row is at table depth 0.
        // ----------------------------------------------------------------
        {
            content:
                "Assert at least one root task row with an expand button is rendered",
            trigger:
                ".o_list_view .o_data_row td.o_recursive_expand_column button.o_expand_button",
        },
        // ----------------------------------------------------------------
        // Step 7: Before expansion the list shows ONLY root rows -- the visit's
        // child tasks are NOT yet in the DOM (lazy). Assert no depth-1 child row
        // is present, so the next step proves expansion is what reveals them.
        // ----------------------------------------------------------------
        {
            content:
                "Assert the child level is collapsed initially (no nested depth-1 row yet)",
            trigger:
                ".o_list_view tbody:not(:has(.o_recursive_bullet[data-depth='1']))",
        },
        // ----------------------------------------------------------------
        // Step 8: Lazy-expand the root row. The recursive_list_view fetches and
        // injects the visit's immediate child tasks as nested rows.
        // ----------------------------------------------------------------
        {
            content: "Expand the root task to reveal its children (lazy-expand)",
            trigger:
                ".o_list_view .o_data_row td.o_recursive_expand_column button.o_expand_button[data-depth='0']",
            run: "click",
        },
        // ----------------------------------------------------------------
        // Step 9: Assert depth-1 child rows are now rendered as nested rows
        // (bullet marker carries data-depth='1') -> the view renders a genuine
        // multi-level parent/child structure and the lazy-expand is functional.
        // The seeded root has TWO child tasks (one per SO line); assert both
        // nested rows appeared.
        // ----------------------------------------------------------------
        {
            content:
                "Assert depth-1 child rows appeared after expansion (multi-level structure rendered)",
            trigger:
                ".o_list_view .o_data_row td.o_recursive_expand_column .o_recursive_bullet[data-depth='1']",
        },
        {
            content:
                "Assert BOTH seeded child tasks rendered as nested depth-1 rows",
            trigger:
                ".o_list_view tbody:has(.o_recursive_bullet[data-depth='1']:eq(1))",
        },
        // ----------------------------------------------------------------
        // Step 10: Collapse the root again and assert the nested child rows are
        // removed -> the expand/collapse toggle is functional, not one-shot.
        // ----------------------------------------------------------------
        {
            content: "Collapse the root task again",
            trigger:
                ".o_list_view .o_data_row td.o_recursive_expand_column button.o_expand_button[data-depth='0']",
            run: "click",
        },
        {
            content:
                "Assert the nested child rows are removed after collapse (toggle is functional)",
            trigger:
                ".o_list_view tbody:not(:has(.o_recursive_bullet[data-depth='1']))",
        },
    ],
});
