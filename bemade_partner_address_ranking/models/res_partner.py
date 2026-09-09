# Copyright (C) 2024 Bemade Inc. (<https://www.bemade.org>).
# License LGPL-3 or later (http://www.gnu.org/licenses/lgpl).
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


# Key used to store the per-request ranking cache on the cursor.
_RANKING_CACHE_KEY = "bemade_partner_address_ranking"


class Partner(models.Model):
    _inherit = "res.partner"

    is_favorite_invoice = fields.Boolean(
        string="Default invoice address",
        default=False,
        help=(
            "When set, this address is selected as the default invoice address"
            " on new sales orders for the parent company, overriding"
            " usage-based ranking."
        ),
    )
    is_favorite_delivery = fields.Boolean(
        string="Default delivery address",
        default=False,
        help=(
            "When set, this address is selected as the default delivery address"
            " on new sales orders for the parent company, overriding"
            " usage-based ranking."
        ),
    )

    @api.constrains("is_favorite_invoice", "is_favorite_delivery", "commercial_partner_id")
    def _check_unique_favorite_per_company(self):
        for partner in self:
            for flag in ("is_favorite_invoice", "is_favorite_delivery"):
                if not partner[flag]:
                    continue
                siblings = self.search_count(
                    [
                        ("commercial_partner_id", "=", partner.commercial_partner_id.id),
                        (flag, "=", True),
                        ("id", "!=", partner.id),
                    ]
                )
                if siblings:
                    raise ValidationError(
                        _(
                            "Only one contact per company can be marked as %s.",
                            self._fields[flag].string,
                        )
                    )

    # ------------------------------------------------------------------
    # Public helper
    # ------------------------------------------------------------------

    def _invalidate_ranking_cache(self):
        """Clear the per-cursor ranking cache for all commercial partners in
        *self*.  Call this after any write that would change ranking results
        (favorite flag change, SO confirmation, SO cancellation).
        """
        cache = getattr(self.env.cr, _RANKING_CACHE_KEY, None)
        if cache is None:
            return
        for partner in self:
            commercial_id = partner.commercial_partner_id.id
            for addr_type in ("invoice", "delivery"):
                cache.pop((commercial_id, addr_type), None)

    def write(self, vals):
        res = super().write(vals)
        if vals.keys() & {"is_favorite_invoice", "is_favorite_delivery", "parent_id"}:
            self._invalidate_ranking_cache()
        return res

    def _get_ranked_address_ids(self, addr_type):
        """Return a list of partner ids for *self* (a company or any partner)
        ordered by:
          1. Favorite flag for *addr_type* (0 or 1 entry).
          2. Usage-count descending on confirmed/done sales orders.
          3. Stock ``address_get`` fallback id.

        Results are deduplicated and the list is memoised per
        ``(commercial_partner_id, addr_type)`` on ``self.env.cr`` for the
        lifetime of the current database cursor (i.e. one request / one test
        transaction).  This avoids repeated ``_read_group`` calls when
        ``name_search`` fires multiple times while the user types.

        :param str addr_type: ``'invoice'`` or ``'delivery'``
        :return: list of int (partner ids), highest-priority first.
        """
        commercial = self.commercial_partner_id
        cache_key = (commercial.id, addr_type)
        cache = getattr(self.env.cr, _RANKING_CACHE_KEY, None)
        if cache is None:
            cache = {}
            setattr(self.env.cr, _RANKING_CACHE_KEY, cache)
        if cache_key in cache:
            return cache[cache_key]

        result = self._compute_ranked_address_ids(commercial, addr_type)
        cache[cache_key] = result
        return result

    @api.model
    def _compute_ranked_address_ids(self, commercial, addr_type):
        """Do the actual ranking computation (no caching layer)."""
        # 1. Favorite id (at most one due to constraint)
        flag = "is_favorite_invoice" if addr_type == "invoice" else "is_favorite_delivery"
        favorite = self.search(
            [
                ("commercial_partner_id", "=", commercial.id),
                (flag, "=", True),
            ],
            limit=1,
        )
        favorite_ids = [favorite.id] if favorite else []

        # 2. Usage-ranked ids from confirmed/done SOs
        so_field = "partner_invoice_id" if addr_type == "invoice" else "partner_shipping_id"
        groups = self.env["sale.order"].sudo()._read_group(
            domain=[
                ("partner_id.commercial_partner_id", "=", commercial.id),
                (so_field, "!=", False),
                ("state", "in", ("sale", "done")),
            ],
            groupby=[so_field],
            aggregates=["__count"],
            order="__count DESC",
        )
        ranked_ids = [g[0].id for g in groups]

        # 3. Stock address_get fallback
        fallback_id = commercial.address_get([addr_type])[addr_type]

        # Merge: favorite first, then ranked, then fallback — deduplicated
        seen = set()
        ordered = []
        for pid in favorite_ids + ranked_ids + [fallback_id]:
            if pid not in seen:
                seen.add(pid)
                ordered.append(pid)

        return ordered

    # ------------------------------------------------------------------
    # name_search override
    # ------------------------------------------------------------------

    @api.model
    @api.readonly
    def name_search(self, name="", args=None, operator="ilike", limit=100):
        """Override to surface ranked / favorite addresses at the top of
        Many2one dropdowns when the picker is opened in a company-address
        context (i.e. when the SO view sets
        ``context={'partner_address_ranking': True}`` on the field).

        The explicit-context approach (Plan B from the design) is used
        because it is the only reliable signal that distinguishes an SO
        address picker from any other ``res.partner`` picker that happens to
        filter by ``parent_id``.

        Early-out: if the context key is absent we delegate to super()
        unchanged, so global partner pickers are completely unaffected.
        """
        if not self.env.context.get("partner_address_ranking"):
            return super().name_search(name=name, args=args, operator=operator, limit=limit)

        addr_type = self.env.context.get("partner_address_ranking")
        if addr_type not in ("invoice", "delivery"):
            # Unrecognised value — fall back to default behaviour
            return super().name_search(name=name, args=args, operator=operator, limit=limit)

        # Run the standard search to respect the active text filter + domain.
        base_results = super().name_search(name=name, args=args, operator=operator, limit=limit)
        if not base_results:
            return base_results

        # Determine the commercial partner from context or from args.
        #
        # ``default_parent_id`` is the key that matters in practice: the stock
        # sale.order form sets it on both address fields
        # (``context="{... 'default_parent_id': partner_id}"``) and puts NO
        # domain on them, so it is the only signal the real picker ever sends.
        # ``default_commercial_partner_id`` is kept for callers that set it
        # explicitly; the args scan below covers views that do constrain the
        # field by domain.
        commercial_id = self.env.context.get(
            "default_commercial_partner_id"
        ) or self.env.context.get("default_parent_id")
        if not commercial_id:
            # Try to detect from args: ('parent_id', '=', X)
            for leaf in (args or []):
                if (
                    isinstance(leaf, (list, tuple))
                    and len(leaf) == 3
                    and leaf[0] in ("parent_id", "commercial_partner_id")
                    and leaf[1] in ("=", "child_of")
                ):
                    candidate = self.browse(leaf[2])
                    commercial_id = candidate.commercial_partner_id.id
                    break

        if not commercial_id:
            return base_results

        # ``commercial_id`` may be any partner in the company tree (the SO sets
        # the customer, which is usually but not always the commercial parent),
        # so normalise before ranking.
        commercial = self.browse(commercial_id).commercial_partner_id
        if not commercial:
            return base_results
        ranked_ids = commercial._get_ranked_address_ids(addr_type)
        if not ranked_ids:
            return base_results

        # Fetch the ranked addresses in their OWN query rather than picking them
        # out of ``base_results``.
        #
        # ``base_results`` has already been truncated to ``limit`` (the web
        # client sends limit=8 for a Many2one dropdown) and that page is ordered
        # by display_name. On any real database a company's own addresses are
        # almost never inside the first 8 names alphabetically, so reordering in
        # place finds nothing to promote and silently returns the unranked page.
        # Re-querying restricted to ``ranked_ids`` keeps the caller's domain and
        # typed text applied while making promotion independent of the limit
        # window.
        ranked_matching = super().name_search(
            name=name,
            args=list(args or []) + [("id", "in", ranked_ids)],
            operator=operator,
            limit=None,
        )
        rank_of = {pid: i for i, pid in enumerate(ranked_ids)}
        ranked_matching.sort(key=lambda pair: rank_of.get(pair[0], len(rank_of)))

        ranked_set = set(ranked_ids)
        others = [pair for pair in base_results if pair[0] not in ranked_set]
        reordered = ranked_matching + others

        # Honour limit
        return reordered[:limit] if limit else reordered
