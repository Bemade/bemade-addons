from odoo import models, fields, api, _
import requests
from bs4 import BeautifulSoup


class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_odoo_partner = fields.Boolean(string="Is Odoo Partner", default=False)
    is_odoo_user = fields.Boolean(string="Is Odoo User", default=False)

    @api.model
    def get_odoo_partner(self):
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
            partner_name = soup.find(id="partner_name")
            address_div = soup.find('span', itemprop='streetAddress')
            email_div = soup.find('span', itemprop='email')
            phone_div = soup.find('span', itemprop='telephone')
            website_div = soup.find('span', itemprop='website')
            if address_div is not None:
                # Extract address components
                address_parts = address_div.get_text(separator="\n").split("\n")
                street_address = address_parts[0]
                city_state_postal = address_parts[len(address_parts)-2].split(', ')
                city = city_state_postal[0]
                state_postal = city_state_postal[1].split(' ')
                state = state_postal[0]
                postal_code = state_postal[1] + state_postal[2]
                country = address_parts[len(address_parts)-1]
            if email_div and email_div.string:
                email = email_div.string
            if phone_div and phone_div.string:
                phone = phone_div.string
            if website_div and website_div.string:
                website = website_div.string

            # self.env['res.partner'].create({
            #     'name': partner_name,
            #     'street': street_address,
            #     'city': city,
            #     'state_id': state,
            #     'zip': postal_code,
            #     'country_id': country,
            #     'email': email,
            #     'phone': phone,
            #     'website': website,
            #     'is_odoo_partner': True,
            # })