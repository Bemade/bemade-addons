/** @odoo-module **/

import tour from 'web_tour.tour';

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
    run: 'text Test Tag Name',
}, {
    content: 'Set the partner',
    trigger: 'div[name="partner_location_id"] div div input',
    run: 'text Test Partner Company',
}, {
    content: 'Click the partner in the dropdown',
    trigger: 'li a.dropdown-item:contains(Test Partner Company)',
}, {
    content: 'Save',
    trigger: 'button.o_form_button_save',
}
// Fill in the required fields, including creating a new Client Location and PID Tag
// Navigate to the client location, then to the client, making sure that the equipment and client location links appear

// Now make another one, but from the Partner interface
// Navigate to Service > Clients > Clients
// Search for and open the test client
// On the "Locations" tab, add a location
// Open the location and add a new Equipment to its equipment list

// Create a task in the test project
])