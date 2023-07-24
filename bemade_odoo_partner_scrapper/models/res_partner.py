from odoo import models, fields, api, _
import requests
from bs4 import BeautifulSoup
import logging
from base64 import b64encode
import re

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_odoo_partner = fields.Boolean(string="Is Odoo Partner", default=False, tracking=True)
    is_odoo_user = fields.Boolean(string="Is Odoo User", default=False, tracking=True)
    odoo_name = fields.Char(string="Name on Odoo")
    odoo_note = fields.Html(string="Note on Odoo")
    odoo_id = fields.Char(string="ID on Odoo")
    odoo_url = fields.Char(string="Odoo Partner URL", tracking=True, index=True)
    odoo_page = fields.Html(string="Odoo Partner/Referral Page")
    odoo_page_update = fields.Date(string="Odoo Page Update")
    odoo_partner_type = fields.Selection(
        [('learning', 'Learning'),
         ('ready', 'Ready'),
         ('silver', 'Silver'),
         ('gold', 'Gold')],
        string="Partner Type",
        tracking=True)

    @api.model
    def change_color_on_kanban(self):
        for record in self:
            color = 0
            if record.odoo_partner_type == 'learning':
                color = 2
            elif record.odoo_partner_type == 'ready':
                color = 10
            elif record.odoo_partner_type == 'silver':
                color = 7
            elif record.odoo_partner_type == 'gold':
                color = 3
            else:
                if record.is_odoo_user:
                    color = 4
            record.color = color

    color = fields.Integer('Color Index', compute="change_color_on_kanban")

    def set_image_from_url(self, url):
        response = requests.get(url)
        if response.status_code == 200:
            self.image_1920 = b64encode(response.content).decode('utf-8')
            _logger.info(f"Image for {self.name} set from {url}")
        else:
            raise ValueError('Could not download image: got response code {}'.format(response.status_code))

    @api.model
    def get_odoo_partner(self):

        def extract_client_data(soup):
            odoo_name = soup.find(id='partner_name').text
            odoo_note = soup.find('div', class_='col-lg-8 mt32')

            main_image = soup.find('img', {'class': 'img img-fluid d-block mx-auto mb16'})
            image_link = main_image['src']

            exist_client = self.env['res.partner'].search([('odoo_name', '=', odoo_name)])

            if not exist_client:
                exist_client = exist_client.create({
                    'name': odoo_name,
                    'is_company': True,
                    'odoo_name':odoo_name,
                    'odoo_note':odoo_note,
                    'is_odoo_user': True,
                    'odoo_page': soup,
                })
                exist_client.set_image_from_url(image_link)
                _logger.info(f"Client {exist_client.name} created")

            return exist_client

        def process_partner_relation(partner, client):
            if partner.id != client.id:
                self.env['res.partner.relation'].create({
                    'left_partner_id' : partner.id,
                    'right_partner_id' : client.id,
                    'type_id' : self.env.ref('bemade_odoo_partner_scrapper.rel_type_odoo_partner').id
                })
                _logger.info(f"Partner {partner.name} Odoo Partner of {client.name}")
            else:
                _logger.info(f"Partner {partner.name} is the same as client {client.name}")

        def extract_partner_data(url):
            page = requests.get("https://www.odoo.com" + url)
            soup = BeautifulSoup(page.content, 'html.parser')

            partner_data = {}

            partner_data['name'] = soup.find(id="partner_name").text
            partner_type = soup.find('h3', class_='col-lg-12 text-center text-muted')

            if partner_type and partner_type.span:
                partner_data['odoo_partner_type'] = partner_type.span.text.strip().lower()

            partner_data['odoo_name'] = soup.find(id="partner_name").text
            address_div = soup.find('span', itemprop='streetAddress')
            email_div = soup.find('span', itemprop='email')
            phone_div = soup.find('span', itemprop='telephone')
            website_div = soup.find('span', itemprop='website')

            main_image = soup.find('img', {'class': 'img img-fluid d-block mx-auto mb16'})
            image_link = main_image['src']

            clients_url = set()
            for link in soup.find_all('a'):
                href = link.get('href')
                if href is not None:
                    # Ignore any URL containing 'country/canada-36'
                    if '/customers/' in href:
                        # Add to set. Duplicates will be ignored automatically.
                        clients_url.add(href)

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

            partner_data['email'] = email_div.string if email_div and email_div.string else False
            partner_data['phone'] = phone_div.string if phone_div and phone_div.string else False
            partner_data['website'] = website_div.string if website_div and website_div.string else False
            partner_data['is_odoo_partner'] = True
            partner_data['is_odoo_user'] = True
            partner_data['is_company'] = True
            partner_data['image_link'] = image_link
            partner_data['clients_url'] = clients_url

            if state_data:
                country_id = self.env['res.country'].search([('code', '=', 'CA')]).id
                partner_data['state_id'] = self.env['res.country.state'].search([('code', '=', state_data),('country_id', '=', country_id)]).id

            partner_data = {k: v for k, v in partner_data.items() if v is not False}

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
            # page = requests.get("https://www.odoo.com" + partner_url)
            # soup = BeautifulSoup(page.content, 'html.parser')

            odoo_partner = extract_partner_data(partner_url)
            _logger.info(f"Processing {odoo_partner['name']}")

            image_url = False
            if odoo_partner['image_link']:
                image_url = odoo_partner['image_link']
                del odoo_partner['image_link']
                _logger.info(f"Image for {odoo_partner['name']} set from {image_url}")

            if odoo_partner['clients_url']:
                clients_url = odoo_partner['clients_url']
            else:
                clients_url = set()

            if 'clients_url' in odoo_partner:
                del odoo_partner['clients_url']

            exist_odoo_name = self.env['res.partner'].search([('odoo_name', '=', odoo_partner['odoo_name'])])
            if exist_odoo_name:
                _logger.info(f"Partner Odoo Name {odoo_partner['name']} already exist")
                new_partner = exist_odoo_name
            else:
                exist_email = self.env['res.partner'].search([('email', '=', odoo_partner['email'])]) if 'email' in odoo_partner else False
                if exist_email:
                    _logger.info(f"Partner Email {odoo_partner['name']} already exist")
                    new_partner = exist_email
                else:
                    exist_phone = self.env['res.partner'].search([('phone', '=', odoo_partner['phone'])]) if 'phone' in odoo_partner else False
                    if exist_phone:
                        _logger.info(f"Partner Phone {odoo_partner['name']} already exist")
                        new_partner = exist_phone
                    else:
                        _logger.info(f"Partner {odoo_partner['name']} created")
                        new_partner = self.env['res.partner'].create(odoo_partner)
                        if image_url:
                            new_partner.set_image_from_url(image_url)

            for client_url in clients_url:
                if 'http' not in client_url:
                    exist_url = self.env['res.partner'].search([('odoo_url', '=', client_url)])
                # add condition on odoo_date, actually not pulling data if date exist
                    if exist_url and exist_url.odoo_page:
                        soup = exist_url.odoo_page
                        _logger.info(f"Client {exist_url.name} reloading soup from db")
                    else:
                        print("https://www.odoo.com" + client_url)
                        page = requests.get("https://www.odoo.com" + client_url)
                        soup = BeautifulSoup(page.content, 'html.parser')
                        _logger.info(f"Client {exist_url.name} read from odoo.com")

                    client = extract_client_data(soup)
                    process_partner_relation(new_partner, client)
