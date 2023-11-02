# -*- coding: utf-8 -*-

import json
import logging
import requests
import binascii
from requests.auth import HTTPBasicAuth
from odoo.exceptions import ValidationError

from odoo import fields, models, api, _, exceptions
from datetime import date, timedelta, datetime
import holidays
import pytz
from timezonefinder import TimezoneFinder
import phonenumbers
from typing import List

_logger = logging.getLogger('Gls Canada')


class DeliveryCarrier(models.Model):
    _inherit = 'delivery.carrier'

    delivery_type = fields.Selection(selection_add=[("gls_canada", "GLS Canada")],
                                     ondelete={'gls_canada': 'set default'})

    gls_canada_packaging_id = fields.Many2one('stock.package.type',
                                              string="Default Package Type")

    gls_canada_payment_type = fields.Selection([('Prepaid', 'Prepaid'),
                                                ('ThirdParty', 'ThirdParty'),
                                                ('Collect', 'Collect')],
                                               string='Gls canada payment type',
                                               help="Please select GLS Canada payment type")
    gls_canada_delivery_type = fields.Selection([('AIR', 'AIR'),
                                                 ('GRD', 'GRD')],
                                                string='Gls canada delivery type',
                                                help="Please select GLS Canada delivery type")
    gls_canada_unit_measurement = fields.Selection([('K', 'kg (implies cm)'),
                                                    ('L', 'lb (implies inch)'),
                                                    ('KC', 'kg-cm'), ('KM', 'kg-meter'),
                                                    ('LI', 'lb-inch'),
                                                    ('LF', 'lb-feet'), ],
                                                   string='Unit Of Measurement')
    parcel_type = fields.Selection([('Barrel', 'Barrel - freight'),
                                    ('Bundle', 'Bundle - freight'),
                                    ('Box', 'Box - freight'),
                                    ('Crate', 'Crate - freight'),
                                    ('FullLoad', 'FullLoad - freight'),
                                    ('Piece', 'Piece - freight'),
                                    ('Skid', 'Skid - freight'),
                                    ('Tube', 'Tube - freight'),
                                    ('Other', 'Other - freight'),
                                    ('Box', 'Box - Parcel Canada'),
                                    ('Envelope', 'Envelope - Parcel Canada'),
                                    ('Other', 'Other - Parcel Canada'),
                                    ('Mixed', 'Mixed - Parcel Canada')],
                                   string='Parcel Type')
    return_label = fields.Boolean("Required Return Label ?")
    category = fields.Selection([('Parcel', 'Parcel'),
                                 ('Freight', 'Freight'),
                                 ('Distribution', 'Distribution'),
                                 ('Logistics', 'Logistics'), ],
                                string='Gls canada category type')
    appointment_type = fields.Selection([('Scheduled', 'Scheduled'),
                                         ('Required', 'Required')])

    def gls_canada_rate_shipment(self, order):
        """
        Estimate the cost of a shipment from a sales order. Called by rate_shipment in
        delivery/models/delivery_carrier.py.

        :param order: ResultSet of sale.order records, all for the same recipient and from the same warehouse
        :return:
        """

        Estimate = self.env['gls.canada.shipping.estimate']

        sender = order.warehouse_id.partner_id
        consignee = order.partner_shipping_id
        billing_account = order.delivery_billing_account
        weight = sum([
            (line.product_id.weight * line.product_uom_qty) for line in
            order.order_line if not line.is_delivery
        ])
        data = {
            "sender": {
                "postalCode": sender.zip or '',
                "provinceCode": sender.state_id and sender.state_id.code or '',
                "countryCode": sender.country_id and sender.country_id.code or '',
            },
            "consignee": {
                "postalCode": consignee.zip or '',
                "provinceCode": consignee.state_id and consignee.state_id.code or '',
                "countryCode": consignee.country_id and consignee.country_id.code or '',
            },
            "billing": self.company_id.gls_canada_billing_number or '',
            "paymentType": self.gls_canada_payment_type,
            "deliveryType": self.gls_canada_delivery_type,

            "unitOfMeasurement": self.gls_canada_unit_measurement,

            "parcels": [
                {
                    "id": "1",
                    "parcelType": self.parcel_type,
                    "quantity": "1",
                    "weight": weight,
                    "length": self.gls_canada_packaging_id.packaging_length or 0,
                    "depth": self.gls_canada_packaging_id.height or 0,
                    "width": self.gls_canada_packaging_id.width or 0,
                    # "FCA_Class": "100.00",

                    # "requestReturnLabel": False,
                }
            ],
            "category": self.category,

        }
        if self.category == "Freight":
            if self.appointment_type == 'Scheduled':
                data.update({"appointment": {
                    "type": self.appointment_type,
                    "date": order.commitment_date.strftime(
                        "%Y-%m-%d") if self.appointment_type == "Scheduled" else '',
                    "time": order.commitment_date.strftime(
                        "%H:%M") if self.appointment_type == "Scheduled" else '',
                }})
            # if self.appointment_type != 'Scheduled':
            else:
                data.update({"appointment": {
                    "type": self.appointment_type,
                    "phone": consignee.phone or ''
                }})

        data = json.dumps(data)
        _logger.info("Rate Request Data %s" % data)
        username = self.company_id.gls_canada_username
        password = self.company_id.gls_canada_password
        headers = {"Content-Type": "application/json"}
        api_url = "%s/rate" % (self.company_id.gls_canada_api_url)
        response_data = requests.post(url=api_url, headers=headers,
                                      auth=HTTPBasicAuth(username, password),
                                      data=data)
        _logger.info("Rate response %s" % response_data.content)
        try:
            if response_data.status_code in [200, 201]:
                response_body = response_data.json()
                _logger.info(response_body)
                existing_records = Estimate.search(
                    [('sale_order_id', '=', order and order.id)])
                existing_records.sudo().unlink()
                if isinstance(response_body.get('rates'), dict):
                    response_body = [response_body.get('rates')]
                for response_dict in response_body.get('rates'):
                    Estimate.sudo().create(
                        {
                            'account_type': response_dict.get('accountType'),
                            'rate_type': response_dict.get('rateType'),
                            'total_charge': response_dict.get('total'),
                            'sale_order_id': order and order.id
                        }
                    )
                gls_canada_charge_id = Estimate.search(
                    [('sale_order_id', '=', order and order.id)], order='total_charge',
                    limit=1)
                order.gls_canada_shipping_charge_id = gls_canada_charge_id and gls_canada_charge_id.id
                return {'success': True,
                        'price': gls_canada_charge_id and gls_canada_charge_id.total_charge or 0.0,
                        'error_message': False, 'warning_message': False}
            else:
                return {'success': False, 'price': 0.0,
                        'error_message': "%s %s" % (response_data, response_data.text),
                        'warning_message': False}
        except Exception as e:
            raise ValidationError(e)

    def gls_canada_send_shipping(self, pickings):
        """ Send the package to the service provider

              :param pickings: A recordset of pickings
              :return list: A list of dictionaries (one per picking) containing of the form::
                               { 'exact_price': price,
                                 'tracking_number': number }
        """
        # See if there are available pickups
        shipments_dict = self._group_pickings_by_warehouse_and_recipient(pickings)
        pickups = self._gls_canada_get_pickups_for_senders(shipments_dict.keys())
        picking_shipment_data_dict = {}
        for sender, recipient_dict in shipments_dict.items():
            for recipient, picks in recipient_dict.items():
                shipping_data, shipment_id = self._gls_canada_send_shipment(picks, pickups.get(sender))
                picking_shipment_data_dict.update(
                    {pick: shipping_data for pick in picks})
                pickup_id = pickups.get(sender)
                if pickup_id:
                    self._add_shipment_to_pickup(shipment_id, pickup_id)
                if not pickups.get(sender):
                    pickup_time = self._get_pickup_time(sender)
                    pickup_id = self._gls_canada_schedule_pickup(picks[0].shipper,
                                                                 picks.mapped('shipment_id'),
                                                                 pickup_time)
                picks.pickup_id = pickup_id
        return [picking_shipment_data_dict[picking] for picking in pickings]

    def _add_shipment_to_pickup(self, shipment_id, pickup_id):
        endpoint = f'/pickup/{pickup_id}/add-shipment/{shipment_id}'
        response = self._gls_canada_api_call(endpoint, "POST", {})
        if response.status_code != 200:
            self._raise_gls_error(endpoint, response)

    def gls_canada_cancel_shipment(self, pickings):
        """This Method is used for cancel shipment from odoo to matkahuolto"""
        api_url = "%s/shipment/%s" % (
            self.company_id.gls_canada_api_url, pickings.shipment_id)
        username = self.company_id.gls_canada_username
        password = self.company_id.gls_canada_password
        headers = {"Content-Type": "application/json"}
        response_body = requests.request(method="DELETE", url=api_url, headers=headers,
                                         auth=HTTPBasicAuth(username, password))
        _logger.info("Cancel Shipment Response %s" % response_body.content)
        if response_body.status_code in [200, 201]:
            _logger.info("Shipment Cancel Successfully")
            return True
        else:
            raise ValidationError(response_body.content)

    def _gls_canada_shipping_request_data(self, pickings):
        parcel_data = []
        counter = 0
        for package in pickings.package_ids:
            counter += 1
            parcel_data.append({
                "id": counter,
                "parcelType": self.parcel_type,
                "quantity": "1",
                "weight": package.shipping_weight,
                "length": package.package_type_id.packaging_length or '',
                "depth": package.package_type_id.height or '',
                "width": package.package_type_id.width or '',
                # "requestReturnLabel": self.return_label,
            })
        if pickings.weight_bulk:
            counter += 1
            parcel_data.append({
                "id": counter,
                "parcelType": self.parcel_type,
                "quantity": "1",
                "weight": pickings.shipping_weight,
                "length": self.gls_canada_packaging_id.packaging_length or '',
                "depth": self.gls_canada_packaging_id.height or '',
                "width": self.gls_canada_packaging_id.width or '',
                # "requestReturnLabel": self.return_label,
            })

        receiver_address = pickings.partner_id
        shipper_address = pickings.picking_type_id.warehouse_id.partner_id
        sender_contact = pickings[0].shipper
        request_data = {
            "category": self.category,
            "paymentType": self.gls_canada_payment_type,
            "billingAccount": self.company_id.gls_canada_billing_number,
            "sender": self._gls_canada_make_sender_data(shipper_address, sender_contact),
            "consignee": self._gls_canada_make_consignee_data(receiver_address),
            "unitOfMeasurement": self.gls_canada_unit_measurement,
            "parcels": parcel_data,
            "deliveryType": self.gls_canada_delivery_type,
        }
        # if self.return_label == True:
        #     request_data.update({"returnAddress": {"contact": {
        #         "fullName": shipper_address.name or '',
        #         "language": "en",
        #         "email": "example@dicom.com",
        #         "department": "",
        #         "telephone": shipper_address.phone or '',
        #         "extension": ""
        #     }
        #     }})
        # if shipper_address.country_id and shipper_address.country_id.code != receiver_address.country_id.code:
        #     request_data.update(
        #         {"internationalDetails": {"descriptionOfGoods": 'Workspace123', "isDicomBroker": 'true', "products": [
        #             {
        #                 "id": "17451",
        #                 "Quantity": 1
        #             }
        #         ]
        #                                   }})
        _logger.info("Shipping Request Data %s" % request_data)
        return request_data

    def _gls_canada_get_pickups_for_senders(self, senders) -> dict:
        """
        Get a dict matching each sender to any already existing pickups today (or next
        business day). If no matching pickup exists, the sender is not added to the keys
        of the dict and a pickup will need to be created for it elsewhere.
        :param senders: The recordset of partner_ids matching the pickup locations
        :return: dict of the form {sender: "pickup ID"}
        """
        endpoint = "/pickup/list"
        # First, group the senders by country and state so that holidays can be properly
        # handled for each location.
        locales = set()
        for sender in senders:
            locales.add((sender.country_id, sender.state_id))
        sender_groups = [[sender for sender in senders if
                          (sender.country_id, sender.state_id) == locale] for locale in
                         locales]
        senders_to_pickups_dict = {}
        # For each group sharing a locale, get pickups for the next working day
        for sender_group in sender_groups:
            pickup_date = self._get_pickup_time(sender_group[0])
            request_data = {
                'category': self.category,
                'pickupDate': pickup_date.strftime("%Y-%m-%d"),
            }
            response = self._gls_canada_api_call(endpoint, "GET", request_data)
            _logger.info("GLS Response status code:%s" % response.status_code)
            if response.status_code == 401:
                raise ValidationError(
                    _("Username or password is incorrect for GLS Canada."))
            elif response.status_code == 204:  # No pickups scheduled
                return {}
            pickups = response.json() if response else []
            for pickup in pickups:
                street = pickup['sender']['addressLine1']
                zip = pickup['sender']['postalCode'].replace(' ', '')
                matching_senders = [sender for sender in sender_group if
                                    (sender.street == street
                                     and sender.zip.replace(' ', '') == zip)]
                senders_to_pickups_dict.update({
                    sender: pickup for sender in matching_senders
                })
        return senders_to_pickups_dict

    @api.model
    def _group_pickings_by_warehouse_and_recipient(self, pickings) -> dict:
        """
        Transform a list of pickings into a dict of the form::

            { sender_partner : { recipient_partner :  recordset(pickings) } }
        :param pickings: The recordset of pickings to be arranged
        :return: dict as described above
        """
        shipments = {pick.picking_type_id.warehouse_id.partner_id: {} for pick in
                     pickings}
        for sender in shipments.keys():
            matching_pickings = pickings.filtered(lambda p:
                                                  p.picking_type_id.warehouse_id.partner_id == sender)
            for pick in matching_pickings:
                recipient = pick.partner_id
                if recipient in shipments[sender]:
                    shipments[sender][recipient] |= pick
                else:
                    shipments[sender].update({recipient: pick})
        return shipments

    def _gls_canada_schedule_pickup(self, sender_contact, shipments: List[str],
                                    pickup_time: datetime, office_close='16:00'):
        shipment = self._load_shipment(shipments[0])
        sender = shipment['sender']
        contact = shipment['sender']['contact']
        endpoint = '/pickup'
        ready_time = pickup_time - timedelta(hours=1)
        request_data = {
            "shipments": [{'id': shipment} for shipment in shipments],
            "contact": self._gls_canada_make_contact_data(sender_contact)['contact'],
            "officeClose": office_close,
            "date": pickup_time.strftime("%Y-%m-%d"),
            "ready": pickup_time.strftime("%H:%M"),
            "category": self.category,
            "location": "SH",
        }
        """ Location is pickup location:
          * SS: Basement
          * RC: ground floor
          * PH: home
          * MR: mail room
          * MB: mailbox
          * BU: office
          * OT: other
          * SH: shipping
        """
        response = self._gls_canada_api_call(endpoint, 'POST', request_data)
        if response.status_code == 201:  # pickup created
            response_body = response.json()
            return response_body.get('ID')
        else:
            self._raise_gls_error(endpoint, response)

    def _load_shipment(self, shipment):
        endpoint = f"/shipment/{shipment}"
        response = self._gls_canada_api_call(endpoint, "GET", {})
        return response.json()

    def _gls_canada_send_shipment(self, pickings, pickup_id):
        """
        Create a new shipment for all the packages in the pickings and assign this
        shipment to the pickup_id submitted. If successful, the shipping label is
        retrieved from GLS and attached to each picking as a PDF.

        :param pickings: The iterable of pickings to be shipped. These must all be from
                         the sender matching the pickup_id submitted and to the same
                         recipient.
        :param pickups: The pickups that are already scheduled for the sender. The first will be used.
        :param pickup: The pickup_id of the pickup that is already scheduled with GLS.
        :return: Tuple containing The shipment data (see _gls_canada_send_shipping)
                 and the shipment ID returned from GLS
        """
        endpoint = "/shipment"
        request_data = self._gls_canada_shipping_request_data(pickings)
        response = self._gls_canada_api_call(endpoint, "POST", request_data)

        _logger.info("Shipping Response %s" % response.content)
        # response_body = self.shipment_response()
        if response.status_code in [200, 201]:
            response_body = response.json()
            _logger.info("Json Response %s " % response_body)
            parcel_tracking_numbers = []
            for parcel_tracking_number in response_body.get(
                    'parcelTrackingNumbers'):
                parcel_tracking_numbers.append(parcel_tracking_number)
            pickings.parcel_tracking_numbers = ', '.join(
                parcel_tracking_numbers)
            pickings.shipment_id = response_body.get('ID')
            master_tracking_number = response_body.get('trackingNumber')
            # print label code
            self._gls_canada_get_label(master_tracking_number, pickings)
            return {'exact_price': 0.0,
                    'tracking_number': master_tracking_number}, response_body.get("ID")
        else:
            self._raise_gls_error(endpoint, response)

    def _gls_canada_get_label(self, master_tracking_number, pickings):
        endpoint = f"/shipment/label/{pickings.shipment_id}"
        headers = {
            'Accept': 'application/pdf',  # TODO: implement application/zpl here
            "Content-Type": "application/json",
        }
        response = self._gls_canada_api_call(endpoint, "GET", {},
                                             headers=headers)
        _logger.info("Label Response %s" % response)
        log_message = f"<b>Tracking Numbers:</b> {master_tracking_number}"
        pickings.message_post(body=log_message,
                              attachments=[(f"Label GLS Canada {pickings.name}.pdf",
                                            response.content)])

    @classmethod
    def _gls_canada_make_sender_data(cls, sender, sender_contact):
        phone_parsed = phonenumbers.parse(
            sender_contact.phone) if sender_contact.phone else ''
        contact_data = cls._gls_canada_make_contact_data(sender_contact)
        return {
            "addressLine1": sender.street or '',
            "addressLine2": sender.street2 or '',
            "city": sender.city or '',
            "provinceCode": sender.state_id and sender.state_id.code or '',
            "postalCode": sender.zip or '',
            "countryCode": sender.country_id and sender.country_id.code or '',
            "customerName": sender.name or '',
            "contact": contact_data['contact']
        }

    @classmethod
    def _gls_canada_make_contact_data(self, partner):
        """
        Build a dict of the form { "contact": { ... GLS contact params ... } } from
        the given partner.
        :param partner: A single res_partner record.
        :return:
        """
        phone_parsed = phonenumbers.parse(partner.phone) if partner.phone else ''
        return {
            "contact": {
                "fullName": partner.name or '',
                "language": partner.lang and partner.lang.split('_')[0] or '',
                "email": partner.email or '',
                "telephone": phone_parsed and phone_parsed.national_number or '',
                "extension": phone_parsed and phone_parsed.extension or '',
            }
        }

    @classmethod
    def _gls_canada_make_consignee_data(cls, partner_id):
        if partner_id.parent_id and partner_id.parent_id.name:
            parent = partner_id.parent_id
            receiver_company_name = parent.name
            receiver_contact_name = partner_id.name or ''
        else:
            receiver_company_name = partner_id.name or ''
            receiver_contact_name = ''
        return {
            "addressLine1": partner_id.street or '',
            "addressLine2": partner_id.street2 or '',
            # "streetType": "AVE",
            # "streetDirection": "N",
            # "suite": "10",
            "city": partner_id.city or '',
            "provinceCode": partner_id.state_id and partner_id.state_id.code or '',
            "postalCode": partner_id.zip or '',
            "countryCode": partner_id.country_id and partner_id.country_id.code or '',
            "customerName": receiver_company_name,
            "contact": {
                "fullName": receiver_contact_name,
                "language": "en",
                "email": partner_id.email or '',
                "department": "",
                "telephone": partner_id.phone or '',
                "extension": ""
            }
        }

    def _gls_canada_api_call(self, endpoint: str, method: str, request_data: dict,
                             headers: dict = {"Content-Type": "application/json"},
                             ) -> requests.Response:
        """
        Make a call to the GLS Canada API using the credentials set on the current
        company_id


        :param endpoint: The endpoint to use, such as "/pickup/list"
        :param method:  The request method to use, typically "GET" or "POST"
        :param headers: Request headers
        :param request_data:
        :return: A list of dicts matching the GLS Canada API response specifications
        """
        request_data = json.dumps(request_data)
        try:
            api_url = "%s%s" % (
                self.company_id and self.company_id.gls_canada_api_url, endpoint)
            _logger.info("Sending GLS Canada request %s" % request_data)
            username = self.company_id.gls_canada_username
            password = self.company_id.gls_canada_password
            if method == "GET":
                response_body = requests.get(url=api_url, params=request_data,
                                             headers=headers,
                                             auth=HTTPBasicAuth(username, password))
            elif method == "DELETE":
                response_body = requests.delete(url=api_url, params=request_data,
                                                headers=headers,
                                                auth=HTTPBasicAuth(username, password))
            else:
                response_body = requests.request(method=method, url=api_url,
                                                 data=request_data, headers=headers,
                                                 auth=HTTPBasicAuth(username, password))
            _logger.info(f"GLS Canada Response Status Code: {response_body.status_code}")
            _logger.info("GLS Canada API Response: %s" % response_body.content)
            return response_body
        except Exception as e:
            raise ValidationError(e)

    @api.model
    def gls_canada_get_tracking_link(self, picking):
        """This method is used for track you parcel"""
        return "https://www.gls-canada.com/en/express/tracking"

    @api.model
    def _get_pickup_time(cls, sender, closing_time='16:00',
                         earliest_pickup='12:00') -> datetime:
        """
        Generate a pickup time within working hours and not on holidays, based on the
        sender's localization (time zone) and closing and starting times.

        :param sender: res_partner representing the sender location, used for holidays
        :param closing_time: closing time to determine if datetime.now() is after the
            workday's closing time, as a string formatted '%H:%M'.
        :param earliest_pickup: earliest time of day for pickups at the sender location
        :return: Today if today is a business day, the next business day otherwise.
        """
        # In theory all sender addresses are from Canada, but this is a more reusable
        # tool and doesn't introduce any extra dependencies for generalizing to all
        # locales.
        if not sender.partner_latitude or not sender.partner_longitude:
            if not sender.geo_localize():
                _logger.warning(f'Sender address for {sender.name} could not be '
                                f'geolocated for time zone information. Server time zone'
                                f' used instead.')
        localized = sender.partner_latitude and sender.partner_longitude
        now = datetime.now() + timedelta(minutes=30)
        if localized:
            tz_name = TimezoneFinder().timezone_at(lng=sender.partner_longitude,
                                                   lat=sender.partner_latitude)
            tz = pytz.timezone(tz_name)
            now = now.astimezone(tz=tz)
        close_h, close_m = closing_time.split(':')
        start_h, start_m = earliest_pickup.split(':')
        closing = datetime(year=now.year, month=now.month, day=now.day,
                           hour=int(close_h), minute=int(close_m)).astimezone(tz)
        starting = datetime(year=now.year, month=now.month, day=now.day,
                            hour=int(start_h), minute=int(start_m)).astimezone(tz)
        #  If past closing time, move to next day at starting time
        if now > closing:
            now = starting + timedelta(days=1)
        # If before starting time, move to current day starting time
        if now < starting:
            now = starting
        local_holidays = holidays.country_holidays(sender.country_id.code,
                                                   sender.state_id.code)
        while now.date() in local_holidays or now.weekday() in (5, 6):
            now += timedelta(days=1)
        return now

    @api.model
    def _raise_gls_error(cls, endpoint, response):
        raise ValidationError(_(f"Got an error from GLS endpoint {endpoint}\n"
                                f"Response: {response.content}"))
