import logging

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """Create OUs for existing top-level company partners on module installation."""
    _logger.info("Creating Organizational Units for existing company partners...")

    # Find all top-level company partners without an OU
    partners = env["res.partner"].search(
        [
            ("is_company", "=", True),
            ("parent_id", "=", False),
        ]
    )

    ou_model = env["organizational.unit"]
    created_count = 0

    for partner in partners:
        # Check if OU already exists for this partner
        existing_ou = ou_model.search([("owner_id", "=", partner.id)], limit=1)
        if not existing_ou:
            ou_model.create(
                {
                    "name": partner.name,
                    "owner_id": partner.id,
                    "user_id": partner.user_id.id if partner.user_id else False,
                }
            )
            created_count += 1

    _logger.info(f"Created {created_count} Organizational Units for existing partners.")
