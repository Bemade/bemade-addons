from odoo.tests import TransactionCase, tagged
import datetime
import pytz

@tagged('-at_install', 'post_install')
class TestGeoRouter(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.apikey = cls.env['base.geo_router']._get_api_key()

    def test_distance_time_basic(self):
        bemade, montreal = self._generate_partners()

        distance, time = self.env['base.geo_router'].get_driving_distance_time(bemade, montreal)

        self.assertTrue(20 < distance < 40)
        self.assertTrue(12 < time < 60)

    def test_time_traffic(self):
        bemade, montreal = self._generate_partners()
        est = pytz.timezone('US/Eastern')
        today_naive = datetime.date.today()
        today = datetime.datetime(today_naive.year, today_naive.month, today_naive.day, 8, 30, tzinfo=est)
        arrival_time_local = today + datetime.timedelta(days=(2 - today.weekday()) % 7)
        arrival_time_utc = arrival_time_local.astimezone(pytz.utc)
        arrival_time = arrival_time_utc.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        print(arrival_time)
        
        distance, time = self.env['base.geo_router'].get_driving_distance_time(bemade, montreal,
                                                                               arrival_time=arrival_time)

        self.assertTrue(25 < time < 90)

    @classmethod
    def _generate_partners(self):
        bemade = self.env['res.partner'].create({
            'name': 'Bemade Inc.',
            'street': '255 North Montcalm Blvd.',
            'city': 'Candiac',
            'zip': 'J5R 3L6',
            'state_id': self.env.ref('base.state_ca_qc').id,
            'country_id': self.env.ref('base.ca').id,
        })
        montreal = self.env['res.partner'].create({
            'name': 'City of Montreal',
            'street': '220 East René-Lévesque Blvd.',
            'city': 'Montreal',
            'zip': 'H2X 3A7',
            'state_id': self.env.ref('base.state_ca_qc').id,
            'country_id': self.env.ref('base.ca').id,
        })
        return bemade, montreal
