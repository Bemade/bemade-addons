from odoo import models, fields, api, _
import requests
from bs4 import BeautifulSoup
import logging

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_odoo_partner = fields.Boolean(string="Is Odoo Partner", default=False, tracking=True)
    is_odoo_user = fields.Boolean(string="Is Odoo User", default=False, tracking=True)
    odoo_name = fields.Char(string="Name on Odoo", tracking=True)
    odoo_id = fields.Char(string="ID on Odoo", tracking=True)
    odoo_url = fields.Char(string="Odoo Partner URL", tracking=True, index=True)

    @api.model
    def get_odoo_partner(self):

        def extract_partner_data(url):
            page = requests.get("https://www.odoo.com" + url)
            soup = BeautifulSoup(page.content, 'html.parser')

            partner_data = {}

            partner_data['name'] = soup.find(id="partner_name").text

            partner_type = soup.find('h3', class_='col-lg-12 text-center text-muted')
            if partner_type and partner_type.span:
                partner_data['partner_type'] = partner_type.span.text.strip()

            partner_data['odoo_name'] = soup.find(id="partner_name").text
            address_div = soup.find('span', itemprop='streetAddress')
            email_div = soup.find('span', itemprop='email')
            phone_div = soup.find('span', itemprop='telephone')
            website_div = soup.find('span', itemprop='website')
            state_data = None

            if address_div is not None:
                # Extract address components
                address_parts = address_div.get_text(separator="\n").split("\n")
                partner_data['street'] = address_parts[0]
                city_state_postal = address_parts[len(address_parts) - 2].split(', ')

                if city_state_postal != [',']:
                    partner_data['city'] = city_state_postal[0]
                    state_postal = city_state_postal[1].split(' ')
                    if len(state_postal) == 3 and len(state_postal[2]) == 3:
                        partner_data['zip'] = state_postal[1] + state_postal[2]
                        state_data = state_postal[0]
                    elif len(state_postal) == 2 and state_postal[1]:
                        if len(state_postal[1]) == 6:
                            partner_data['zip'] = state_postal[1]
                            state_data = state_postal[0]
                        if len(state_postal[1]) == 3:
                            if len(state_postal[0]) == 2:
                                partner_data['zip'] = state_postal[1]
                                state_data = state_postal[0]
                            else:
                                partner_data['zip'] = state_postal[0] + state_postal[1]
                    else:
                        if len(state_postal[0]) == 6:
                            partner_data['zip'] = state_postal[0]
                        else:
                            state_data = state_postal[0]

                # partner_data['country'] = address_parts[len(address_parts) - 1]

            partner_data['email'] = email_div.string if email_div and email_div.string else ''
            partner_data['phone'] = phone_div.string if phone_div and phone_div.string else ''
            partner_data['website'] = website_div.string if website_div and website_div.string else ''
            partner_data['is_odoo_partner'] = True
            partner_data['is_odoo_user'] = True

            if state_data:
                print(state_data)
                country_id = self.env['res.country'].search([('code', '=', 'CA')]).id
                partner_data['state_id'] = self.env['res.country.state'].search([('code', '=', state_data),('country_id', '=', country_id)]).id

            return partner_data

        # Load the webpage at the given url
        page = requests.get("https://www.odoo.com/fr_FR/partners/country/canada-36")
        # Parse the HTML content
        soup = BeautifulSoup(page.content, 'html.parser')
        div = soup.find(id="ref_content")
        partners_url = set()
        other_pages = set()

        for link in div.find_all('a'):
            href = link.get('href')
            if href is not None:
                # Ignore any URL containing 'country/canada-36'
                if '/page/' in href:
                    # Add to set. Duplicates will be ignored automatically.
                    other_pages.add(href)

        for link in div.find_all('a'):
            href = link.get('href')
            if href is not None and href != '':
                # Ignore any URL containing 'country/canada-36'
                if 'country/canada-36' not in href:
                    # Add to set. Duplicates will be ignored automatically.
                    partners_url.add(href.split('#', 1)[0].split('?', 1)[0])

        for other_page in other_pages:
            page = requests.get("https://www.odoo.com" + other_page)
            soup = BeautifulSoup(page.content, 'html.parser')
            div = soup.find(id="ref_content")
            for link in div.find_all('a'):
                href = link.get('href')
                if href is not None and href != '':
                    # Ignore any URL containing 'country/canada-36'
                    if 'country/canada-36' not in href:
                        # Add to set. Duplicates will be ignored automatically.
                        partners_url.add(href.split('#', 1)[0].split('?', 1)[0])

        for partner_url in partners_url:
            page = requests.get("https://www.odoo.com" + partner_url)
            soup = BeautifulSoup(page.content, 'html.parser')

            print (partner_url)
            odoo_partner = extract_partner_data(partner_url)
            print (odoo_partner)

            # partner_name = soup.find(id="partner_name").text
            # address_div = soup.find('span', itemprop='streetAddress')
            # email_div = soup.find('span', itemprop='email')
            # phone_div = soup.find('span', itemprop='telephone')
            # website_div = soup.find('span', itemprop='website')
            # if address_div is not None:
            #     # Extract address components
            #     address_parts = address_div.get_text(separator="\n").split("\n")
            #     street_address = address_parts[0]
            #     city_state_postal = address_parts[len(address_parts) - 2].split(', ')
            #
            #     if city_state_postal != [',']:
            #         city = city_state_postal[0]
            #         state_postal = city_state_postal[1].split(' ')
            #
            #         if len(state_postal) == 3 and len(state_postal[2]) == 3:
            #             postal_code = state_postal[1] + state_postal[2]
            #             state = state_postal[0]
            #         elif len(state_postal) == 2 and state_postal[1]:
            #             if len(state_postal[1]) == 6:
            #                 postal_code = state_postal[1]
            #                 state = state_postal[0]
            #             if len(state_postal[1]) == 3:
            #                 if len(state_postal[0]) == 2:
            #                     postal_code = state_postal[1]
            #                     state = state_postal[0]
            #                 else:
            #                     postal_code = state_postal[0] + state_postal[1]
            #                     state = ''
            #         else:
            #             if len(state_postal[0]) == 6:
            #                 postal_code = state_postal[0]
            #                 state = ''
            #             else:
            #                 postal_code = ''
            #                 state = state_postal[0]
            #     else:
            #         city = ''
            #         state = ''
            #         postal_code = ''
            #     #                   state = state_postal[0]
            #     #                postal_code = state_postal[1] + state_postal[2]
            #     country = address_parts[len(address_parts) - 1]
            # if email_div and email_div.string:
            #     email = email_div.string
            # else:
            #     email = ''
            # if phone_div and phone_div.string:
            #     phone = phone_div.string
            # else:
            #     phone = ''
            # if website_div and website_div.string:
            #     website = website_div.string
            # else:
            #     website = ''

            _logger.info(f"Processing {odoo_partner['name']} with email {odoo_partner['email']} and phone {odoo_partner['phone']} and website {odoo_partner['website']}")

            exist_odoo_name = self.env['res.partner'].search([('odoo_name', '=', odoo_partner['odoo_name'])])
            if not exist_odoo_name:
                exist_email = self.env['res.partner'].search([('email', '=', odoo_partner['email'])])
                if not exist_email:
                    exist_phone = self.env['res.partner'].search([('phone', '=', odoo_partner['phone'])])
                    if not exist_phone:
                        exist_website = self.env['res.partner'].search([('website', '=', odoo_partner['website'])])

                        if not exist_website or odoo_partner['website'] == '':
                            if odoo_partner['website'] == '':
                                del odoo_partner['website']
                            self.env['res.partner'].create(odoo_partner)
                            # self.env['res.partner'].create({
                            #     'name': partner_name,
                            #     'street': street_address,
                            #     'city': city,
                            #     'state_id': state_id.id if state_id else False,
                            #     'zip': postal_code,
                            #     'country_id': country_id.id if country_id else False,
                            #     'email': email,
                            #     'phone': phone,
                            #     'website': website,
                            #     'is_odoo_partner': True,
                            # })