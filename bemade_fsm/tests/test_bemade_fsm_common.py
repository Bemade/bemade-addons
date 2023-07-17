from odoo.tests.common import TransactionCase, tagged
from odoo import Command


@tagged("-at_install", "post_install")
class BemadeFSMBaseTest(TransactionCase):

    @classmethod
    def _generate_project_manager_user(cls, name, login):
        group_ids = cls.__get_user_groups()
        user_group_project_manager = cls.env.ref('project.group_project_manager')
        user_group_fsm_manager = cls.env.ref('industry_fsm.group_fsm_manager')
        group_ids.append(user_group_fsm_manager.id)
        group_ids.append(user_group_project_manager.id)

        return cls.__generate_user(name, login, group_ids)

    @classmethod
    def _generate_project_user(cls, name, login):
        group_ids = cls.__get_user_groups()
        return cls.__generate_user(name, login, group_ids)

    @classmethod
    def __generate_user(cls, name, login, group_ids):
        return cls.env['res.users'].with_context({'no_reset_password': True}).create({
            'name': name,
            'login': login,
            'password': login,
            'email': f"{login}@test.co",
            'groups_id': [Command.set(group_ids)]
        })

    @classmethod
    def __get_user_groups(cls):
        user_group_employee = cls.env.ref('base.group_user')
        user_group_project_user = cls.env.ref('project.group_project_user')
        user_group_fsm_user = cls.env.ref('industry_fsm.group_fsm_user')
        user_group_sales_user = cls.env.ref('sales_team.group_sale_salesman')
        user_group_sales_manager = cls.env.ref('sales_team.group_sale_manager')
        user_product_customer = cls.env.ref('customer_product_code.group_product_customer_code_user')

        group_ids = [user_group_employee.id,
                     user_group_project_user.id,
                     user_group_fsm_user.id,
                     user_group_sales_manager.id,
                     user_group_sales_user.id, ]
        if user_product_customer:
            group_ids.append(user_product_customer.id)
        return group_ids

    @classmethod
    def _generate_partner(cls, name: str = 'Test Company', company_type: str = 'company', parent=None,
                          location_type='other'):
        """ Generates a partner with basic address filled in.

        :param name: The partner's name.
        :param company_type: The type of partner, either 'company' or 'person' are accepted."""
        return cls.env['res.partner'].create({
            'name': name,
            'company_type': company_type,
            'street': '123 Street St.',
            'city': 'Montreal',
            'state_id': cls.env.ref('base.state_ca_qc').id,
            'country_id': cls.env.ref('base.ca').id,
            'parent_id': parent and parent.id or False,
            'type': location_type,
        })

    @classmethod
    def _generate_sale_order(cls, partner=None, client_order_ref='Test Order', equipment=None):
        partner = partner or cls._generate_partner()
        return cls.env['sale.order'].create({
            'partner_id': partner.id,
            'client_order_ref': client_order_ref,
            'equipment_id': equipment and equipment.id or False,
        })

    @classmethod
    def _generate_sale_order_line(cls, sale_order, product, qty=1.0, uom=None, price=100.0, tax_id=False):
        return cls.env['sale.order.line'].create({
            'order_id': sale_order.id,
            'product_id': product.id,
            'product_uom_qty': qty,
            'product_uom': uom and uom.id or cls.env.ref("uom.product_uom_hour").id,
            'price_unit': price,
            'tax_id': tax_id,
        })

    @classmethod
    def _generate_equipment(cls, name='test equipment', partner=None):
        return cls.env['bemade_fsm.equipment'].create({
            'name': name,
            'partner_location_id': partner and partner.id or False,
        })

    @classmethod
    def _generate_product(cls, name='Test Product', product_type='service', service_tracking='task_global_project',
                          project=None, task_template=None, service_policy='delivered_manual', uom=None):
        if 'project' in service_tracking and not project:
            project = cls.env.ref("industry_fsm.fsm_project")
        uom_id = uom and uom.id or cls.env.ref("uom.product_uom_hour").id or False
        return cls.env['product.product'].create({
            'name': name,
            'type': product_type,
            'service_tracking': service_tracking,
            'project_id': service_tracking in ('task_global_project', 'project_only') and project.id or False,
            'project_template_id': service_tracking == 'task_in_project' and project.id or False,
            'task_template_id': task_template and task_template.id or False,
            'service_policy': service_policy,
            'uom_id': uom_id,
            'uom_po_id': uom_id,
        })

    @classmethod
    def _generate_fsm_project(cls, name='Test Project'):
        return cls.env['project.project'].create({
            'name': name,
            'allow_material': True,
            'allow_timesheets': True,
            'allow_subtasks': True,
            'allow_quotations': True,
            'allow_worksheets': True,
            'is_fsm': True,
        })

    @classmethod
    def _generate_task_template(cls, parent=None, structure=None, names=None, planned_hours=1,
                                equipment=None):
        """ Generates a task template with the specified structure and naming.

        :param parent: The parent task template for the top-level task template being generated
        :param structure: A list of integers describing the number of tasks for each level of descendants. An empty
                          list represents only one top-level task template. If no structure is given, an empty list
                          will be used in its place.
        :param names: The name prefixes to be given to the task templates at each level. Each prefix will be followed
                      by a sequential integer for its level. Child 1, Child 2, Grandchild 1, etc. If no names argument
                      is passed, a default ['Task Template'] argument will be used.
        :param planned_hours: The number of planned hours for the top-level task template being generated.
        :param equipment: The equipment to add as linked equipment to the task template."""
        if not names:
            names = ['Task Template']
        if not structure:
            structure = []
        if len(structure) != len(names) - 1:
            raise ValueError("The length of the structure argument must contain exactly one element less than the "
                             "names argument.")
        name = names.pop(0)
        template = cls.env['project.task.template'].create({
            'name': name,
            'parent': parent and parent.id or False,
            'planned_hours': planned_hours,
            'equipment_ids': [Command.set(equipment and [equipment.id] or [])],
        })
        parent = template
        while structure:
            subtasks = []
            for i in range(0, structure[0]):
                subtasks.append(cls.env['project.task.template'].create({
                    'parent': parent.id,
                    'name': names[0] + f" {i}",
                }))
            structure.pop(0)
            names.pop(0)
            parent = subtasks[0]
        return template
