/** @odoo-module **/

import tour from 'web_tour.tour';

const SO_NAME = "TEST ORDER 2"
const PRODUCT_NAME = "Test Product 3"
tour.register('sale_order_tour', {
        test: true,
        url: '/web',
    },
    [tour.stepUtils.showAppsMenuItem(), {
        content: 'Navigate to the Service menu',
        trigger: '.o_app[data-menu-xmlid="sale.sale_menu_root"]',
    }, {
        content: 'Search for the sales order',
        trigger: 'input.o_searchview_input',
        run: `text ${SO_NAME}`,
    }, {
        content: 'Validate Search',
        trigger: '.o_menu_item.o_selection_focus',
        run: 'click',
    }, {
        content: 'Open the test order',
        trigger: `.o_data_cell[name="client_order_ref"]:contains(${SO_NAME})`,
    }, {
        content: 'Click the view tasks button',
        trigger: 'button[name="action_view_task"]',
    }, /*{
        content: 'Click the first task',
        trigger: `div.o_kanban_record:has(span:contains(${PRODUCT_NAME}))`,
    },*/ {
        content: 'Click on the ready to invoice button',
        trigger: 'button[name="action_fsm_validate"]',
        extra_trigger: `li.breadcrumb-item.active:has(span:contains(${PRODUCT_NAME}))`
    }, {
        content: 'View the SO',
        trigger: 'button[name="action_view_so"]',
        // extra_trigger: 'button[title="Current state"]:contains(Done)',
    }
    ]);
