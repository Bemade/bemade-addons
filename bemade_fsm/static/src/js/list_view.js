/** @odoo-module **/

import ListController from 'web.ListController';
import ListView from 'web.ListView';
const viewRegistry = require('web.view_registry')

const ProjectListController = ListController.extend({
    buttons_template: 'project.ListView.buttons',
    custom_events: _.extend({}, ListController.prototype.custom_events, {
        create_from_template: '_onCreateFromTemplate',
    }),
    _onCreateFromTemplate(ev) {
        ev.stopPropagation();
        const record = this.model.get(this.handle, {raw: true});
        this.do_action({
            type: 'ir.actions.act_window',
            res_model: 'project.task.from.template.wizard',
            views: [[false, 'form']],
            target: 'new',
            context: {...record.context, res_model: 'project.task'},
        });
    },
    renderButtons ($node) {
        self = this;
        this._super.apply(this, arguments);
        this.$buttons.on('click', 'button.o_list_button_add_from_template', this._onCreateFromTemplate.bind(this))
    },
})

const ProjectListView = ListView.extend({
    config: _.extend({}, ListView.prototype.config, {
        Controller: ProjectListController,
    })
});

viewRegistry.add('project_list', ProjectListView)