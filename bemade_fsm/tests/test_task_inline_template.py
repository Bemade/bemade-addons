from .test_bemade_fsm_common import BemadeFSMBaseTest
from odoo.tests import tagged, Form
from odoo import Command


@tagged("post_install", "-at_install")
class TaskInlineTemplateTest(BemadeFSMBaseTest):
    """Acceptance tests for task 3611 — inline template_id expansion.

    Acceptance criteria (01-requirements.md):
      1. project.task subtask list exposes a template_id field.
      2. On create/write, a subtask row with template_id set is populated from
         the template (name, description, assignees, tags, planned_hours, …),
         reusing the wizard's value-prep logic.
      3. A template with child templates expands the full subtree (grandchildren
         included).
      4. The existing modal-wizard flow continues to work unchanged.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.project = cls.env.ref("industry_fsm.fsm_project")
        cls.assignee = cls._generate_project_user("Alice", "alice")
        cls.customer = cls._generate_partner(name="Inline Customer")

    def _new_parent_task(self):
        return self.env["project.task"].create(
            {
                "name": "Parent Task",
                "project_id": self.project.id,
                "partner_id": self.customer.id,
            }
        )

    def test_inline_template_id_populates_subtask(self):
        """AC 2: a subtask row carrying template_id is populated from the
        template on create — name, tags, assignees, planned_hours — and the
        transient template_id is cleared afterwards."""
        parent = self._new_parent_task()
        tag = self.env["project.tags"].create({"name": "Inline Tag"})
        template = self._generate_task_template(names=["Tmpl"], planned_hours=5)
        template.write(
            {
                "assignees": [Command.set(self.assignee.ids)],
                "tags": [Command.set(tag.ids)],
                "description": "<p>Tmpl description</p>",
            }
        )

        child = self.env["project.task"].create(
            {
                "parent_id": parent.id,
                "project_id": self.project.id,
                "name": "placeholder",
                "template_id": template.id,
            }
        )

        self.assertEqual(child.name, template.name)
        self.assertEqual(child.tag_ids, tag)
        self.assertEqual(child.user_ids, self.assignee)
        self.assertEqual(child.allocated_hours, template.planned_hours)
        # Transient template_id cleared after instantiation (idempotency).
        self.assertFalse(child.template_id)

    def test_inline_template_expands_full_subtree(self):
        """AC 3: a template with child templates (and a grandchild) expands the
        full subtree via the inline create path — something a plain onchange
        could not do."""
        parent = self._new_parent_task()
        template = self._generate_task_template(
            names=["Tmpl", "Child", "Grandchild"], structure=[2, 1]
        )

        child = self.env["project.task"].create(
            {
                "parent_id": parent.id,
                "project_id": self.project.id,
                "name": "placeholder",
                "template_id": template.id,
            }
        )

        # The row got the two child templates as subtasks.
        self.assertEqual(len(child.child_ids), len(template.subtasks))
        # The first child template had one grandchild template — created too.
        self.assertEqual(
            len(child.child_ids[0].child_ids),
            len(template.subtasks[0].subtasks),
        )
        self.assertEqual(len(child.child_ids[0].child_ids), 1)
        # Names propagated from the templates.
        self.assertEqual(
            sorted(child.child_ids.mapped("name")),
            sorted(template.subtasks.mapped("name")),
        )
        # Every created task lives in the same project.
        self.assertTrue(
            all(
                t.project_id == self.project
                for t in child | child._get_all_subtasks()
            )
        )

    def test_inline_template_form_path(self):
        """AC 1 + 2 + 3: exercise the real x2many one2many write a user performs
        in the subtask list via the form view — set template_id on a new line and
        save the parent. Catches missing view field / context-default issues."""
        parent = self._new_parent_task()
        tag = self.env["project.tags"].create({"name": "Form Tag"})
        template = self._generate_task_template(
            names=["FormTmpl", "FormChild"], structure=[1]
        )
        template.write({"tags": [Command.set(tag.ids)]})

        with Form(parent, view="project.view_task_form2") as form:
            with form.child_ids.new() as line:
                line.name = "placeholder"
                line.template_id = template

        subtask = parent.child_ids[-1]
        self.assertEqual(subtask.name, template.name)
        self.assertEqual(subtask.tag_ids, tag)
        # Child template was instantiated under the inline subtask.
        self.assertEqual(len(subtask.child_ids), len(template.subtasks))
        self.assertFalse(subtask.template_id)

    def test_inline_template_idempotent_on_later_edit(self):
        """AC 2 (idempotency): after instantiation, editing the subtask (e.g.
        renaming it) does not re-instantiate the template subtree."""
        parent = self._new_parent_task()
        template = self._generate_task_template(
            names=["Tmpl", "Child"], structure=[1]
        )

        child = self.env["project.task"].create(
            {
                "parent_id": parent.id,
                "project_id": self.project.id,
                "name": "placeholder",
                "template_id": template.id,
            }
        )
        n_children = len(child.child_ids)
        self.assertEqual(n_children, len(template.subtasks))

        child.write({"name": "renamed"})

        self.assertEqual(child.name, "renamed")
        # No re-instantiation: the child count is unchanged.
        self.assertEqual(len(child.child_ids), n_children)

    def test_wizard_flow_still_works(self):
        """AC 4: the existing modal-wizard instantiation path
        (create_task_from_self) still produces the full subtree — the additive
        change did not regress the shared helpers."""
        template = self._generate_task_template(
            names=["Task", "Child", "Grandchild"], structure=[2, 1]
        )

        task = template.create_task_from_self(self.project, "My new task")

        self.assertEqual(task.name, "My new task")
        self.assertEqual(len(task.child_ids), len(template.subtasks))
        self.assertEqual(
            len(task.child_ids[0].child_ids),
            len(template.subtasks[0].subtasks),
        )
        self.assertTrue(
            all(
                t.project_id == self.project
                for t in task | task._get_all_subtasks()
            )
        )
