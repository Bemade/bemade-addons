<?xml version="1.0" encoding="UTF-8"?>
<odoo>
    <data>
        <!-- Héritage de la vue formulaire du projet pour ajuster les champs de synchronisation -->
        <record id="view_project_project_form_inherit_sync" model="ir.ui.view">
            <field name="name">project.project.form.inherit.sync.odoo17</field>
            <field name="model">project.project</field>
            <field name="inherit_id" ref="project.view_project"/>
            <field name="arch" type="xml">
                <xpath expr="//sheet" position="inside">
                    <!-- Ajout d'un nouveau séparateur pour les champs de synchronisation -->
                    <group string="Synchronisation Odoo">
                        <field name="customer_odoo_server"/>
                        <field name="customer_username" invisible="customer_odoo_server == False"/>
                        <field name="customer_password" invisible="customer_odoo_server == False"/>
                    </group>
                </xpath>
            </field>
        </record>
    </data>
</odoo>
