from .test_task_template import BemadeFSMBaseTest
from odoo.tests import tagged, Form
from odoo import Command, fields


@tagged("-at_install", "post_install")
class TestSalesOrder(BemadeFSMBaseTest):
    @tagged("-at_install", "post_install")
    def test_order_confirmation_simple_template(self):
        """Confirming the order should create a task in the global project based on the
        task template."""
        partner = self._generate_partner()
        so = self._generate_sale_order(partner=partner)
        task_template = self._generate_task_template(planned_hours=8)
        product = self._generate_product(task_template=task_template)
        sol = self._generate_sale_order_line(so, product=product)

        so.action_confirm()

        task = sol.task_id
        self.assertTrue(task)
        self.assertTrue(task_template.name in task.name)
        self.assertTrue(task_template.planned_hours == task.allocated_hours)

    def test_task_template_tree_order_confirmation(self):
        partner = self._generate_partner()
        so = self._generate_sale_order(partner=partner)
        parent_template = self._generate_task_template(
            structure=[2, 1],
            names=["Parent Template", "Child Template", "Grandchild Template"],
        )
        child_template_1 = parent_template.subtasks[0]
        child_template_2 = parent_template.subtasks[1]
        grandchild_template = parent_template.subtasks[0].subtasks[0]
        product = self._generate_product(task_template=parent_template)
        sol = self._generate_sale_order_line(so, product=product)

        so.action_confirm()

        parent = sol.task_id
        c1, c2 = parent.child_ids
        gc = c1.child_ids[:1]
        self.assertTrue(parent.child_ids and len(parent.child_ids) == 2)
        self.assertTrue(parent_template.name in parent.name)
        self.assertEqual(child_template_1.name, c1.name)
        self.assertEqual(child_template_2.name, c2.name)
        self.assertTrue(c1.child_ids and len(c1.child_ids) == 1)
        self.assertEqual(grandchild_template.name, gc.name)

    def test_order_confirmation_single_equipment(self):
        """The equipment selected on the SO should transfer to the task."""
        partner = self._generate_partner()
        equipment = self._generate_equipment(partner=partner)
        so = self._generate_sale_order(partner=partner, equipment=equipment)
        task_template = self._generate_task_template(planned_hours=8)
        product1 = self._generate_product(task_template=task_template)
        product2 = self._generate_product()
        sol1 = self._generate_sale_order_line(so, product=product1)
        sol2 = self._generate_sale_order_line(so, product=product2)

        so.action_confirm()

        task1 = sol1.task_id
        task2 = sol2.task_id
        self.assertEqual(task1.equipment_ids[0], equipment)
        self.assertEqual(task2.equipment_ids[0], equipment)

    def test_order_confirmation_multiple_equipment(self):
        """All equipment items should flow from the sale order line to the final task"""
        partner = self._generate_partner()
        for i in range(5):
            self._generate_equipment(partner=partner)
        sale_order = self._generate_sale_order(
            partner=partner
        )  # No default equipment since more than 3 on partner
        sol1, sol2, sol3 = [
            self._generate_sale_order_line(sale_order=sale_order) for _ in range(3)
        ]
        sol1.equipment_ids = [
            Command.set([partner.equipment_ids[i].id for i in range(2)])
        ]
        sol3.equipment_ids = [
            Command.set([partner.equipment_ids[i].id for i in range(2, 5)])
        ]

        sale_order.action_confirm()

        self.assertEqual(sol1.equipment_ids, sol1.task_id.equipment_ids)
        self.assertEqual(sol2.equipment_ids, sol2.task_id.equipment_ids)
        self.assertEqual(sol3.equipment_ids, sol3.task_id.equipment_ids)

    def test_task_template_with_equipment_flow(self):
        """The equipment selected on a task template should flow down to the task
        created on SO confirmation."""
        partner = self._generate_partner()
        equipment = self._generate_equipment(partner=partner)
        so = self._generate_sale_order(partner=partner)
        task_template = self._generate_task_template(equipment=equipment)
        product = self._generate_product(task_template=task_template)
        sol = self._generate_sale_order_line(so, product=product)

        so.action_confirm()

        self.assertEqual(sol.task_id.equipment_ids[0], equipment)

    def test_sale_order_line_gets_default_equipment(self):
        """Sale order lines created on a SO with default equipment set should inherit
        that default equipment."""
        partner = self._generate_partner()
        self._generate_equipment(partner=partner)
        sale_order = self._generate_sale_order(partner=partner)

        sol = self._generate_sale_order_line(sale_order=sale_order)

        self.assertEqual(sol.equipment_ids, partner.equipment_ids)

    def test_sale_order_gets_correct_default_equipment_from_partner(self):
        """Should pick up equipment from the partner."""
        partner = self._generate_partner()
        self._generate_equipment(partner=partner)

        sale_order = self._generate_sale_order(partner=partner)

        self.assertEqual(sale_order.default_equipment_ids, partner.owned_equipment_ids)

    def test_sale_order_default_equipment_maximum_number(self):
        parent = self._generate_partner()
        child = self._generate_partner(parent=parent)
        for i in range(3):
            self._generate_equipment(partner=child)

        sale_order = self._generate_sale_order(partner=parent)

        self.assertEqual(sale_order.default_equipment_ids, parent.owned_equipment_ids)

    def test_sale_order_no_default_equipment_with_more_than_three_owned_on_partner(
        self,
    ):
        parent = self._generate_partner()
        child = self._generate_partner(parent=parent)
        for i in range(4):
            self._generate_equipment(partner=child)

        sale_order = self._generate_sale_order(partner=parent)

        self.assertEqual(sale_order.default_equipment_ids, self.env["fsm.equipment"])

    def test_sale_order_resets_default_equipment_on_partner_change(self):
        partner_1 = self._generate_partner()
        partner_2 = self._generate_partner()
        self._generate_equipment(partner=partner_1)
        sale_order = self._generate_sale_order(partner_1)
        form = Form(sale_order)

        form.partner_id = partner_2
        form.save()

        self.assertFalse(sale_order.default_equipment_ids)

    def test_sale_order_prioritize_shipping_location_equipments(self):
        parent = self._generate_partner()
        child = self._generate_partner(parent=parent, location_type="delivery")
        self._generate_equipment(partner=parent)
        self._generate_equipment(partner=child)

        sale_order = self._generate_sale_order(partner=parent, shipping_location=child)

        self.assertEqual(sale_order.default_equipment_ids, child.equipment_ids)

    def test_default_equipment_transfers_to_sale_order_line(self):
        partner = self._generate_partner()
        for i in range(3):
            self._generate_equipment(partner=partner)
        sale_order = self._generate_sale_order(partner=partner)

        for i in range(3):
            self._generate_sale_order_line(sale_order=sale_order)

        for line in sale_order.order_line:
            self.assertEqual(line.equipment_ids, partner.equipment_ids)

    def test_task_mark_done(self):
        """Marking the task linked to a SO line should mark the line delivered.
        Marking sub-tasks done should not."""
        partner = self._generate_partner()
        so = self._generate_sale_order(partner=partner)
        task_template = self._generate_task_template(
            structure=[2], names=["Parent Task", "Subtask"]
        )
        product = self._generate_product(task_template=task_template)
        sol = self._generate_sale_order_line(so, product=product)
        so.action_confirm()
        parent_task = sol.task_id
        subtasks = parent_task._get_all_subtasks()

        # Marking the subtasks done should not increment delivered quantity
        subtasks.action_fsm_validate(True)
        self.assertEqual(sol.qty_delivered, 0)

        # Marking the top-level tasks done should set the delivered quantity to some
        # non-zero value based on the UOM
        parent_task.action_fsm_validate(True)
        self.assertTrue(sol.qty_delivered != 0)

    def test_task_contacts_through_sale_order(self):
        """Make sure the site contacts and work order contacts transfer correctly
        from the SO to the task."""

        partner = self._generate_partner()
        contact1 = self._generate_partner("Site contact", "person", partner)
        contact2 = self._generate_partner("Work order contact", "person", partner)
        partner.write(
            {
                "site_contacts": [Command.set([contact1.id])],
                "work_order_contacts": [Command.set([contact2.id])],
            }
        )
        so = self._generate_sale_order(partner)
        product = self._generate_product()
        sol = self._generate_sale_order_line(sale_order=so, product=product)

        so.action_confirm()

        self.assertEqual(so.work_order_contacts, partner.work_order_contacts)
        self.assertEqual(so.site_contacts, partner.site_contacts)
        self.assertEqual(sol.task_id.work_order_contacts, partner.work_order_contacts)
        self.assertEqual(sol.task_id.site_contacts, partner.site_contacts)

    def test_tasks_created_at_order_confirmation_have_no_assignees(self):
        so, visit, sol1, sol2 = self._generate_so_with_one_visit_two_lines()
        user = self._generate_project_user(name="User", login="login")

        # We test as a specific user since testing as root may not produce the error
        so.with_user(user).action_confirm()

        visit_task = visit.task_id
        subtask1 = visit_task.child_ids[0]
        subtask2 = visit_task.child_ids[1]
        self.assertFalse(visit_task.user_ids)
        self.assertFalse(subtask1.user_ids)
        self.assertFalse(subtask2.user_ids)

    def test_long_line_name_overflows_to_task_description(self):
        so = self._generate_sale_order()
        product = self._generate_product()
        product.description_sale = (
            "This is a long product description.\n"
            "It even spans multiple lines.\n"
            "One could find this annoying in a task name."
        )

        sol = self._generate_sale_order_line(sale_order=so, product=product)

        so.action_confirm()
        task = sol.task_id

        self.assertFalse("This is a long product description." in task.name)
        self.assertFalse("It even spans multiple lines." in task.name)
        self.assertFalse("One could find this annoying in a task name." in task.name)
        self.assertTrue("It even spans multiple lines." in task.description)
        self.assertTrue(
            "One could find this annoying in a task name." in task.description
        )

    def test_subtask_templates_no_description_if_blank_on_template(self):
        so = self._generate_sale_order()
        template = self._generate_task_template(
            structure=[5], names=["Parent", "Child"]
        )
        template.description = ""
        template.subtasks[0].description = "Some fixed description"
        for t in template.subtasks[1:]:
            t.description = ""
        product = self._generate_product(task_template=template)
        sol = self._generate_sale_order_line(sale_order=so, product=product)

        so.action_confirm()

        task = sol.task_id
        self.assertEqual(
            task.child_ids[0].description, template.subtasks[0].description
        )
        for t in task.child_ids[1:]:
            self.assertFalse(t.description)

    def test_duplicate_sale_order_duplicates_visits(self):
        """Duplicated sales orders should have visits tied to their SO lines as in the
        original. The copied visits should not have approximate dates set, however."""
        so, visit, line1, line2 = self._generate_so_with_one_visit_two_lines()

        so2 = so.copy()

        self.assertTrue(so2.visit_ids)
        visit2 = so2.visit_ids[0]
        self.assertEqual(so2.order_line[0].visit_id, visit2)
        self.assertEqual(visit2.label, visit.label)
        self.assertFalse(visit2.approx_date)

    def test_duplicate_sale_order_visits_have_distinct_section_lines(self):
        """When duplicating an SO to create an alternative quotation, visits must be
        duplicated with NEW section lines (not shared with original), and must NOT
        be linked to any existing tasks from the original SO.

        This is the core requirement for "Créer Alternative" functionality:
        - Each visit gets a new section line (duplicated from original)
        - Visits are linked to their own section lines (not the old ones)
        - Visits have no tasks attached (task_ids not copied)
        - Approximate dates are not copied (copy=False on approx_date)
        - Visit labels are preserved

        This ensures the alternative SO can be modified independently of the original,
        and can have its own visits scheduled as new tasks when confirmed.
        """
        so, visit, line1, line2 = self._generate_so_with_one_visit_two_lines()

        # Set approximate date to verify it's not copied
        visit.approx_date = fields.Date.today()

        so2 = so.copy()

        # 1. Verify visit exists on new SO
        self.assertEqual(len(so2.visit_ids), 1, "Alternative SO should have one visit")
        visit2 = so2.visit_ids[0]

        # 2. Verify visits are different records
        self.assertNotEqual(visit, visit2, "Visits should be distinct records")

        # 3. Verify section lines are different (not shared)
        self.assertNotEqual(
            visit.so_section_id, visit2.so_section_id,
            "Visits should have different section lines"
        )
        self.assertEqual(
            visit2.so_section_id.order_id, so2,
            "New visit's section line should belong to the alternative SO"
        )

        # 4. Verify visit label is preserved
        self.assertEqual(visit2.label, visit.label, "Visit label should be preserved")

        # 5. Verify approximate date is NOT copied
        self.assertFalse(visit2.approx_date, "Approximate date should not be copied")

        # 6. Verify new visit has no tasks attached (task_ids is empty)
        self.assertFalse(
            visit2.task_ids, "New visit should not have any tasks attached"
        )
        self.assertFalse(
            visit2.task_id, "New visit should not have a task attached"
        )

        # 7. Verify section lines are linked to new visit correctly
        # The new section line should be linked to the new visit
        self.assertEqual(
            len(so2.order_line), 3,
            "Alternative SO should have 3 lines: section + 2 products"
        )
        section_line = so2.order_line.filtered(lambda l: l.display_type == 'line_section')
        self.assertEqual(len(section_line), 1, "Should have exactly one section line")
        self.assertEqual(
            section_line.visit_id, visit2,
            "Section line should be linked to the new visit"
        )

    def test_duplicate_sale_order_visits_preserve_order_structure(self):
        """When duplicating an SO with multiple visits, the order structure should be
        preserved - each visit should be linked to its own section line, and section
        lines should appear in the same order as in the original SO."""
        so = self._generate_sale_order()
        visit1 = self._generate_visit(sale_order=so, label="First Visit")
        visit2 = self._generate_visit(sale_order=so, label="Second Visit")
        product = self._generate_product()

        # Create lines with specific ordering: visit1 -> line1 -> visit2 -> line2
        line1 = self._generate_sale_order_line(sale_order=so, product=product)
        line2 = self._generate_sale_order_line(sale_order=so, product=product)
        visit1.so_section_id.sequence = 1
        line1.sequence = 2
        visit2.so_section_id.sequence = 3
        line2.sequence = 4

        so2 = so.copy()

        # Verify both visits are duplicated
        self.assertEqual(len(so2.visit_ids), 2, "Alternative SO should have two visits")

        # Verify visits are ordered correctly (by section line sequence)
        so2_visits = so2.visit_ids.sorted(key=lambda v: v.so_section_id.sequence)
        self.assertEqual(so2_visits[0].label, "First Visit")
        self.assertEqual(so2_visits[1].label, "Second Visit")

        # Verify each visit has its own section line
        self.assertNotEqual(
            so2_visits[0].so_section_id, so2_visits[1].so_section_id,
            "Each visit should have its own section line"
        )

        # Verify section lines are not shared with original SO
        original_sections = so.order_line.filtered(lambda l: l.display_type == 'line_section')
        new_sections = so2.order_line.filtered(lambda l: l.display_type == 'line_section')
        for new_section in new_sections:
            self.assertNotIn(
                new_section, original_sections,
                "New sections should not be in original SO"
            )

    def test_confirming_sale_order_creates_visit_if_none_created(self):
        so = self._generate_sale_order()
        so.company_id.create_default_fsm_visit = True
        product = self._generate_product()
        self._generate_sale_order_line(so, product)

        so.action_confirm()

        visit_line = so.order_line.sorted("sequence")[0]
        self.assertTrue(so.visit_ids)
        self.assertEqual(visit_line.visit_id, so.visit_ids)

    def test_confirming_sale_order_with_visit_creates_no_new_lines(self):
        so = self._generate_sale_order()
        so.company_id.create_default_fsm_visit = True
        self._generate_product()
        self._generate_visit(so)

        so.action_confirm()

        self.assertEqual(len(so.visit_ids), 1)

    def test_confirming_sale_order_creates_no_visit_if_setting_off(self):
        so = self._generate_sale_order()
        so.company_id.create_default_fsm_visit = False
        product = self._generate_product()
        self._generate_sale_order_line(so, product)

        so.action_confirm()

        self.assertFalse(so.visit_ids)

    def test_changing_sale_order_customer_follows_to_tasks_and_subtasks(self):
        so = self._generate_sale_order()
        so = self._generate_sale_order()
        so.company_id.create_default_fsm_visit = False
        task_template = self._generate_task_template(
            parent=None,
            structure=[2, 2],
            names=["Parent", "Child", "Grandchild"],
        )
        product = self._generate_product(task_template=task_template)
        sol = self._generate_sale_order_line(so, product)

        so.action_confirm()

        parent_task = sol.task_id
        for task in parent_task._get_all_subtasks() | parent_task:
            self.assertEqual(so.partner_shipping_id, task.partner_id)

        so.write(
            {
                "partner_shipping_id": self.env["res.partner"]
                .create(
                    {
                        "name": "New shipping address",
                        "parent_id": so.partner_id.id,
                        "type": "delivery",
                    }
                )
                .id
            }
        )
        for task in parent_task._get_all_subtasks() | parent_task:
            self.assertEqual(
                so.partner_shipping_id,
                task.partner_id,
                f"{task.name} has a different partner than the SO",
            )

    def test_task_hierarchy_maintained_after_cancel_reconfirm(self):
        """Test that task hierarchy and project assignments are maintained when canceling
        and reconfirming a sale order with a templated FSM product."""
        self.env.user.groups_id |= self.env.ref(
            "account.group_delivery_invoice_address"
        )
        # Create a task template with subtasks
        parent_template = self._generate_task_template(
            structure=[2],  # Two subtasks
            names=["Main Service", "Subtask"],
            planned_hours=8,
        )

        # Create FSM product with template
        product = self._generate_product(task_template=parent_template)

        # Create and confirm sale order
        partner = self._generate_partner()
        partner_2 = self._generate_partner(parent=partner, company_type="person")
        self.assertEqual(partner_2.commercial_partner_id, partner)
        so = self._generate_sale_order(partner=partner)
        sol = self._generate_sale_order_line(so, product=product)
        so.action_confirm()

        # Get initial tasks and verify setup
        main_task = sol.task_id
        self.assertTrue(main_task, "Main task should be created")
        self.assertTrue(main_task.project_id, "Main task should have a project")

        subtasks = main_task.child_ids
        self.assertEqual(len(subtasks), 2, "Should have created 2 subtasks")
        self.assertEqual(so.tasks_count, 1, "Should have only 1 task on confirmation")

        # Verify initial task hierarchy
        initial_project = main_task.project_id
        for subtask in subtasks:
            self.assertEqual(
                subtask.project_id,
                initial_project,
                "Subtask should have same project as main task",
            )
            self.assertFalse(
                subtask.sale_order_id, "Subtask should not be linked to sale order"
            )
            self.assertFalse(
                subtask.sale_line_id, "Subtask should not be linked to sale order line"
            )

        # Store initial names for comparison
        initial_subtask_names = subtasks.mapped("name")

        original_task_names = (main_task | main_task._get_all_subtasks()).mapped("name")
        # Cancel and reconfirm the sale order
        so.with_context(disable_cancel_warning=True).action_cancel()

        so.action_draft()
        so.write({"partner_shipping_id": partner_2.id})
        # Get new tasks
        new_main_task = sol.task_id
        self.assertEqual(
            new_main_task, main_task, "New main task should be same as old"
        )

        new_subtasks = new_main_task.child_ids
        new_subtasks._compute_sale_line()
        self.assertEqual(
            len(new_subtasks), 2, "Should still have 2 subtasks after reconfirmation"
        )
        self.assertFalse(
            new_subtasks.sale_line_id,
            "Subtasks should not be linked to Sale Order Line",
        )
        new_task_names = (new_main_task | new_main_task._get_all_subtasks()).mapped(
            "name"
        )
        self.assertEqual(
            new_task_names, original_task_names, "New task names should be the same"
        )

        # Verify task hierarchy is maintained
        self.assertEqual(
            new_main_task.project_id,
            initial_project,
            "New main task should have same project",
        )

        for subtask in new_subtasks:
            self.assertEqual(
                subtask.project_id,
                initial_project,
                "New subtask should maintain same project as main task",
            )
            self.assertFalse(
                subtask.sale_order_id, "New subtask should not be linked to sale order"
            )
            self.assertFalse(
                subtask.sale_line_id,
                "New subtask should not be linked to sale order line",
            )

        # Verify subtask names are maintained
        self.assertEqual(
            sorted(new_subtasks.mapped("name")),
            sorted(initial_subtask_names),
            "Subtask names should be maintained after reconfirmation",
        )
