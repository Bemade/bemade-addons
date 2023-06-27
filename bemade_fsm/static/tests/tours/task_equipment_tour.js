/** @odoo-module **/

import tour from 'web_tour.tour';
const TEST_COMPANY = "Test Partner Company";
const TEST_EQPT1 = "Test Equipment 1";
const TEST_EQPT2 = "Test Equipment 2";
tour.register('task_equipment_tour', {
        test: true,
        url: '/web',
    }, /* Create a new "Test Equipment" and link it to "Test Partner Company" */
    [tour.stepUtils.showAppsMenuItem(), {
        content: 'Navigate to the Service menu',
        trigger: '.o_app[data-menu-xmlid="industry_fsm.fsm_menu_root"]',
    }, {
        content: 'Navigate to the Clients submenu',
        trigger: 'button.dropdown-toggle[data-menu-xmlid="bemade_fsm.menu_service_client"]',
    }, {
        content: 'Navigate to the Equipment menu',
        trigger: '.dropdown-item[data-menu-xmlid="bemade_fsm.menu_service_client_equipment"]',
    }, {
        content: 'Click the create button',
        trigger: '.o_list_button_add',
        extra_trigger: 'li.breadcrumb-item.active:has(span:contains(Equipment))',
    }, {
        content: 'Add a tag',
        trigger: 'input[name="pid_tag"]',
        run: 'text TestPIDTag',
    }, {
        content: 'Set the name',
        trigger: 'input[name="name"]',
        run: `text ${TEST_EQPT2}`,
    }, {
        content: 'Set the partner',
        trigger: 'div[name="partner_location_id"] div div input',
        run: 'text Test Partner Company',
    }, {
        content: 'Click the partner in the dropdown',
        trigger: `li a.dropdown-item:contains(${TEST_COMPANY})`,
    }, {
        content: 'Save equipment',
        trigger: 'button.o_form_button_save',
    }, {
        /* Navigate to the client and make sure that there are two equipments saved (one from the Python test case) */
        content: 'Navigate to the Clients submenu',
        trigger: 'button.dropdown-toggle[data-menu-xmlid="bemade_fsm.menu_service_client"]',
    }, {
        content: 'Click on the clients submenu',
        trigger: '.dropdown-item[data-menu-xmlid="bemade_fsm.menu_service_client_clients"]',
    }, {
        content: 'Search for the Test Partner Company',
        trigger: 'input.o_searchview_input',
        extra_trigger: 'li.breadcrumb-item.active:has(span:contains(Customers))',
        run: `text ${TEST_COMPANY}`
    }, {
        content: 'Validate Search',
        trigger: '.o_menu_item.o_selection_focus',
        run: 'click',
    }, {
        content: 'Open the test client.',
        trigger: `div.o_kanban_record:has(span:contains(${TEST_COMPANY}))`,
    }, {
        content: 'Click the Field Service tab.',
        trigger: 'a.nav-link:contains(Field Service)',
        extra_trigger: `h1 span.o_field_partner_autocomplete[name="name"]:contains(${TEST_COMPANY})`,
    }, {
        content: 'Make sure we have a first test equipment',
        /*trigger: `div[name="equipment_ids"]:has(td:contains(${TEST_EQPT1}))`,*/
        trigger: `td:contains(${TEST_EQPT1})`,
        run: function() {},
    }, {
        content: 'Make sure we have a second test equipment',
        trigger: `div[name="equipment_ids"]:has(td:contains(${TEST_EQPT2}))`,
        run: function() {},
    }
    ])