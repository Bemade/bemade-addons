# Copyright 2025 Bemade Inc.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

from odoo import api, fields, models


class MailFromAddress(models.Model):
    """Authorized email addresses that can be used as From address in mail composer."""
    _name = "mail.from.address"
    _description = "Authorized From Address"
    _order = "sequence, name"

    name = fields.Char(
        required=True,
        string="Display Name",
        help="Display name for this From address (e.g., 'Customer Service')",
    )
    email = fields.Char(
        required=True,
        string="Email Address",
        help="The email address to use as From address",
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        default=lambda self: self.env.company.id,
    )
    user_ids = fields.Many2many(
        "res.users",
        "mail_from_address_user_rel",
        "address_id",
        "user_id",
        string="Allowed Users",
        help="Users allowed to send from this address. Leave empty for all users.",
    )

    _sql_constraints = [
        ("email_unique", "UNIQUE(email, company_id)", "Email address must be unique per company."),
    ]

    @api.depends("name", "email")
    def _compute_display_name(self):
        """Compute display name in Odoo 18+ style (replaces deprecated name_get)."""
        for record in self:
            record.display_name = f"{record.name} <{record.email}>"

    @api.model
    def _get_allowed_addresses(self, user=None):
        """Return the list of From addresses the user is allowed to use.
        
        If no user is provided, use the current user.
        Addresses with no user_ids restriction are available to all users.
        """
        if user is None:
            user = self.env.user
        
        # Get addresses either with no user restriction or with the user in the list
        domain = [
            ("active", "=", True),
            ("company_id", "in", [False, self.env.company.id]),
            "|",
            ("user_ids", "=", False),
            ("user_ids", "in", [user.id]),
        ]
        return self.search(domain)