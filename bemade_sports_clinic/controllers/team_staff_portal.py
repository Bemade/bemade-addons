from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo import http


class TeamStaffPortal(CustomerPortal):
    def _prepare_home_portal_values(self, counters):
        rtn = super()._prepare_home_portal_values(counters)
        teams_domain = self._prepare_teams_domain()
        players_domain = self._prepare_players_domain(teams_domain)
        rtn['teams_count'] = http.request.env['res.partner'].search_count(teams_domain)
        rtn['players_count'] = http.request.env['sports.patient'].search_count(players_domain)
        return rtn

    def _prepare_teams_domain(self):
        user = http.request.env.user
        partner = http.request.env.user.partner_id
        return [
            ('staff_partner_ids', 'in', partner.id),
            ('type', '=', 'team'),
        ]

    def _prepare_players_domain(self, teams_domain):
        team_ids = http.request.env['res.partner'].search(teams_domain).ids
        return [
            ('team_ids', 'in', team_ids),
        ]

    # @http.route(route=['/my/teams'], type=http, auth='user', website=True)
    # def view_teams(self, ):
    #     pass

