/** @odoo-module */

import tour from 'web_tour.tour';

tour.register('task_template_tour', {
        test: true,
        url: '/web',
    }, /* Make sure the test task is visible via the Project > Task Templates path */
    [tour.stepUtils.showAppsMenuItem(), {
        trigger: '.o_app[data-menu-xmlid="project.menu_main_pm"]',
    }, {
        content: 'Open the task templates list view.',
        trigger: '.o_nav_entry[data-menu-xmlid="durpro_fsm.task_template_menu"]',
    }, {
        content: 'Open the existing task template.',
        trigger: '.o_data_cell:contains("Template 1"):parent()',
    }, {
        content: 'Confirm that the header contains the task title.',
        trigger: 'span[name="name"]:contains("Template 1")',
    }, /* Make sure we can see the task template from the product */
        tour.stepUtils.toggleHomeMenu(),
    {
        content: 'Open the sales menu.',
        trigger: '.o_app[data-menu-xmlid="sale.sale_menu_root"]',
    }, {
        content: 'Open the product dropdown menu.',
        trigger: 'button[data-menu-xmlid="sale.product_menu_catalog"]',
    }, {
        content: 'Click the products menu item.',
        trigger: 'a.dropdown-item[data-menu-xmlid="sale.menu_product_template_action"]',
    }, {
        content: 'Search for the test product.',
        trigger: 'input.o_searchview_input',
        extra_trigger: 'li.breadcrumb-item.active:has(span:contains(Products))',
        run: 'text Test Product 1',
    }, {
        trigger: '.o_menu_item.o_selection_focus',
        content: 'Validate search',
        run: 'click',
    }, {
        content: 'Open the test product.',
        trigger: 'div.o_kanban_record:has(span:contains(Test Product 1))',
    }, {
        content: 'Ensure the product_template_id field is displayed with the "Template 1" mention.',
        trigger: 'a.o_quick_editable[name="task_template_id"]:first-child:contains("Template 1")',
    },
    ])