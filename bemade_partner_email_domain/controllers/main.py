# Import necessary libraries
from odoo import http, _
#from odoo.http import request


# Define a controller class that inherits from http.Controller
class DivisionCompanyController(http.Controller):

    # Decorator to set the routing rules for the method 'select_division_company'.
    # The URL for this method will be '/select_division_company'
    # It has public access and should be used for HTTP requests of type GET.
    @http.route('/select_division_company', website=True, type='http', auth='public')
    def select_division_company(self, partner_id, access_token, division_id, **kwargs):

        # Search the 'res.partner' model for a record with the given partner_id using Super User access rights 
        partner = http.request.env['res.partner'].sudo().search([
            ('id', '=', int(partner_id))
        ])

        # Check if a partner was found with the given ID
        if not partner:
            # If no partner found, render an error page with a translatable error message
            return http.request.render('bemade_partner_email_domain.error_page',
                                       {'error_message': _('The requested partner is not found.')})
        else:
            # If the partner exists and the access token matches, proceed with updating the partner's division
            if access_token and access_token == partner.access_token:
                # Update the partner's parent with the division_id
                partner.write({'parent_id': int(division_id)})

                # Set a confirmation message signaling that the partner has been associated with the division
                confirmation_message = _('Partner %s is associated with the division %s.' % (partner.name, division_id))

                # Render the error page (which in this case acts as a status page) with the confirmation message.
                return http.request.render('bemade_partner_email_domain.error_page',
                                           {'confirmation_message': confirmation_message})
            else:
                # If the access token was not provided or does not match, render an error page with an error message
                return http.request.render('bemade_partner_email_domain.error_page',
                                           {'error_message': _('No Access Token found or not matching for this partner.')})