import os

from geopy.geocoders import Nominatim, GoogleV3
from geopy.extra.rate_limiter import RateLimiter
from random import randint


class Geocoder:

    def __init__(self,proxy,ca_cert) -> None:
        gmaps_api_key = os.environ.get('GMAPS_API_KEY')
        self.__gmaps = GoogleV3(api_key=gmaps_api_key) if gmaps_api_key else None
        user_agent = 'stl-scraper-{}'.format(randint(1, 10000))

        proxy = {'http': proxy,
                      'https': proxy}

        import certifi
        import ssl
        import geopy.geocoders

        ctx = ssl.create_default_context(cafile=ca_cert)
        geopy.geocoders.options.default_ssl_context = ctx
        self.__geolocator = Nominatim(user_agent=user_agent,proxies=proxy)
        self.__osm_reverse_geo = RateLimiter(self.__geolocator.reverse, min_delay_seconds=1)

    def is_city(self, name: str, country: str):
        try:
            location = self.__geolocator.geocode({'city': name, 'country': country})
            if location.raw['type'] == 'city':
                return True
            else:
                return False
        except:
            return False

    def reverse(self, lat: float, lon: float) -> dict | bool:
        """Tries OSM reverse geocoder (Nomatim) first. If it fails, tries Google Maps reverse geocoder (untested)."""
        # Try OSM
        try:
            address = self.__osm_reverse_geo((lat, lon), language='en').raw['address']
            if 'city' in address:
                return address
            if 'town' in address:
                address['city'] = address['town']
                return address
            if 'state' in address:
                address['city'] = address['state']
                return address
        except:
            pass

        # Else try google maps
        if self.__gmaps:
            try:
                address = self.__gmaps.reverse((lat, lon), language='en')
                if 'city' in address:
                    return address
            except:
                pass

        return False
