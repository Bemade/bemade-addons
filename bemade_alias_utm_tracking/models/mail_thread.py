# -*- coding: utf-8 -*-

from odoo import api, models


class MailThread(models.AbstractModel):
    _inherit = "mail.thread"

    @api.model
    def _message_route_process(self, message, message_dict, routes):
        """Fold a tracking alias's UTM defaults into each route's creation values.

        Each route is a tuple ``(model, thread_id, custom_values, user_id,
        alias)``. For a route whose ``alias`` is flagged ``track_utm_source``
        with a source configured, we stamp the alias's UTM source/medium/
        campaign onto the ``custom_values`` dict that core passes to the target
        model's ``message_new`` -> ``create``.

        Guards:
        * only applied to brand-new records (no ``thread_id``); updates to an
          existing thread keep their source;
        * only fields the target model actually has are set (so a non-UTM
          alias target is untouched);
        * never overwrites a value already present in ``custom_values`` (an
          explicit ``alias_defaults`` wins over the config fields).
        """
        new_routes = []
        for route in routes or ():
            model, thread_id, custom_values, user_id, alias = route
            if alias and not thread_id and model in self.env:
                utm_values = alias._get_utm_creation_values()
                if utm_values:
                    target_fields = self.env[model]._fields
                    custom_values = dict(custom_values or {})
                    for field_name, value in utm_values.items():
                        if field_name in target_fields and not custom_values.get(
                            field_name
                        ):
                            custom_values[field_name] = value
                    route = (model, thread_id, custom_values, user_id, alias)
            new_routes.append(route)
        return super()._message_route_process(message, message_dict, new_routes)
