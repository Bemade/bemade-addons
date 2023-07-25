from odoo import models, fields, tools, _, api
from odoo.exceptions import UserError
import requests
import logging
import datetime
from typing import Literal

_logger = logging.getLogger(__name__)


class GeoRouter(models.AbstractModel):
    """ Abstract class used to call Google Route API and convert responses
    into useful distance and route data.
    """
    _name = 'base.geo_router'
    _description = "Geographic Router"

    units = Literal['metric', 'imperial']

    @api.model
    def _get_api_key(self):
        apikey = self.env['ir.config_parameter'].sudo().get_param('base_geolocalize.google_map_api_key')
        if not apikey:
            raise UserError(_(
                "API key for GeoCoding (Places) required.\n"
                "Visit https://developers.google.com/maps/documentation/geocoding/get-api-key for more information."
            ))
        return apikey

    @api.model
    def get_driving_distance_time(self, origin, destination, departure_time: datetime.datetime = None,
                                  arrival_time: datetime.datetime = None, units: units = 'metric',
                                  avoid_tolls=False, avoid_highways=False, avoid_ferries=False) -> (float, float):
        """ Calculates the route between two addresses and returns the distance it either in Kilometers or Miles and
            the time in minutes.

        :param origin: The origin address (res.partner) from which to drive (origin).
        :param destination: The destination address (res.partner).
        :param departure_time: The departure time to use when planning the route (traffic aware).
                               Cannot be set simultaneously with arrival_time.
        :param arrival_time: The arrival time to use when planning the route (traffic aware).
                             Cannot be set simultaneously with departure_time.
        :param units: Type of units to return: 'imperial' for Miles, 'metric' for Kilometers.
        :param avoid_tolls: Whether Google should calculate a route avoiding tolls.
        :param avoid_highways: Whether Google should calculate a route avoiding highways.
        :param avoid_ferries: Whether Google should calculate a route avoiding ferries.
        :returns: tuple(distance: float, time: float)
        """
        if departure_time and arrival_time:
            raise ValueError("Route cannot be calculated with both an arrival time and departure time.")
        apikey = self._get_api_key()
        origin_addr = self.env['base.geocoder'].geo_query_address(street=origin.street, zip=origin.zip,
                                                                  city=origin.city, state=origin.state_id.name,
                                                                  country=origin.country_id.name)
        destination_addr = self.env['base.geocoder'].geo_query_address(street=destination.street, zip=destination.zip,
                                                                       city=destination.city,
                                                                       state=destination.state_id.name,
                                                                       country=destination.country_id.name)
        params = {
            'origin': {
                'address': origin_addr,
            },
            'destination': {
                'address': destination_addr,
            },
            'travelMode': 'DRIVE',
            'computeAlternativeRoutes': False,
            'routeModifiers': {
                'avoidTolls': avoid_tolls,
                'avoidHighways': avoid_highways,
                'avoidFerries': avoid_ferries,
            },
            'languageCode': 'en-US',
            'units': units,
        }
        if departure_time or arrival_time:
            params.update({
                'routingPreference': 'TRAFFIC_AWARE',
                'departureTime' if departure_time else 'arrivalTime': departure_time or arrival_time
            })

        url = "https://routes.googleapis.com/directions/v2:computeRoutes"
        distance_field = 'distanceMeters' if units == 'metric' else 'distanceMiles'
        result = requests.post(url,
                               json=params,
                               headers={'X-Goog-Api-Key': apikey,
                                        'Content-Type': 'application/json',
                                        'X-Goog-FieldMask': f"routes.duration,routes.{distance_field}"}).json()
        if 'routes' not in result:
            _logger.error(f"Failed to retrieve route between {origin_addr} and {destination_addr}. "
                          f"Google response: {result}.")
        route = result['routes'][0]
        distance = (route[distance_field] / 1000) if units == 'metric' else route[distance_field]
        time = int(route['duration'].strip('s')) / 60
        return distance, time
