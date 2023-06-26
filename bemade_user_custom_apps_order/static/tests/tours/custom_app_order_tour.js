/** @odoo-module */

import tour from 'web_tour.tour';

tour.register('custom_app_order_tour', {
        test: true,
        url: '/web',
    }, /* Make sure the test task is visible via the Project > Task Templates path */
    [
        {
            trigger: 'div.o_user_menu button.dropdown-toggle',
        },
        {
            trigger: 'span[data-menu="settings"]:contains(My Profile)'
        },
        {
            trigger: 'a.nav-link:contains(App Order)'
        }
    ])