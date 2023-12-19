/** @odoo-module **/

import KanbanController from 'web.KanbanController';
import KanbanView from 'web.KanbanView';
const viewRegistry = require('web.view_registry')

const ProjectKanbanController = KanbanController.extend({
    buttons_template: 'project.KanbanView.buttons',
    custom_events: _.extend({}, KanbanController.prototype.custom_events, {
        create_from_template: '_onCreateFromTemplate',
    }),
    _onCreateFromTemplate(ev) {
        ev.stopPropagation();
        const record = this.model.get(this.handle, {raw: true});
        let context = record.context;
        context.active_id = record.project_id;
        this.do_action({
            type: 'ir.actions.act_window',
            res_model: 'project.task.from.template.wizard',
            views: [[false, 'form']],
            target: 'new',
            context: {...record.context, res_model: 'project.task'},
        });
    },
    renderButtons ($node) {
        this._super.apply(this, arguments);
        this.$buttons.on('click', 'button.o-kanban-button-new-from-template', this._onCreateFromTemplate.bind(this))
    },
})

const ProjectKanbanView = KanbanView.extend({
    config: _.extend({}, KanbanView.prototype.config, {
        Controller: ProjectKanbanController,
    })
});

viewRegistry.add('project_kanban', ProjectKanbanView)