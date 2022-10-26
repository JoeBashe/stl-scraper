import json
import requests

from logging import Logger
from urllib.parse import urlparse, parse_qs

from stl.endpoint.base_endpoint import BaseEndpoint
from stl.endpoint.calendar import Calendar
from stl.endpoint.explore import Explore
from stl.endpoint.pdp import Pdp
from stl.endpoint.reviews import Reviews
from stl.exception.api import ForbiddenException
from stl.persistence.elastic import Elastic
from stl.persistence import PersistenceInterface


class AirbnbScraperInterface:
    def run(self, *args, **kwargs):
        raise NotImplementedError()


class AirbnbSearchScraper(AirbnbScraperInterface):
    def __init__(self, explore: Explore, pdp: Pdp, reviews: Reviews, persistence: PersistenceInterface, logger: Logger):
        self.__logger = logger
        self.__explore = explore
        self.__geography = {}
        self.__ids_seen = set()
        self.__pdp = pdp
        self.__persistence = persistence
        self.__reviews = reviews

    def run(self, query: str, params: dict):
        listings = []
        url = self.__explore.get_url(query, params)
        data, pagination = self.__explore.search(url)
        self.__geography.update(data['data']['dora']['exploreV3']['metadata']['geography'])
        n_listings = 0
        page = 1
        data_cache = {}
        while pagination.get('hasNextPage'):
            self.__logger.info('Searching page {} for {}'.format(page, query))
            listing_ids = self.__pdp.collect_listings_from_sections(data, data_cache)
            for listing_id in listing_ids:  # request each property page
                if listing_id in self.__ids_seen:
                    self.__logger.warning('Duplicate listing: {}'.format(listing_id))
                    continue  # skip duplicates
                self.__ids_seen.add(listing_id)
                n_listings += 1
                self.__logger.info('Getting data for listing #{}: {}'.format(n_listings, listing_id))
                reviews = self.__reviews.get_reviews(listing_id)
                listings.append(self.__pdp.get_listing(listing_id, data_cache, self.__geography, reviews))

            self.__add_search_params(params, url)
            items_offset = pagination['itemsOffset']
            params.update({'itemsOffset': items_offset})
            url = self.__explore.get_url(query, params)
            data, pagination = self.__explore.search(url)
            page += 1

        self.__persistence.save(query, listings)
        self.__logger.info('Got data for {} listings.'.format(n_listings))

    @staticmethod
    def __add_search_params(params: dict, url: str):
        parsed_qs = parse_qs(urlparse(url).query)
        variables = json.loads(parsed_qs['variables'][0])['request']
        if 'checkin' in variables:
            params['checkin'] = variables['checkin']
            params['checkout'] = variables['checkout']

        if 'priceMax' in variables:
            params['priceMax'] = variables['priceMax']

        if 'priceMin' in variables:
            params['priceMin'] = variables['priceMin']

        if 'ne_lat' in parsed_qs:
            params['ne_lat'] = parsed_qs['ne_lat'][0]

        if 'ne_lng' in parsed_qs:
            params['ne_lng'] = parsed_qs['ne_lng'][0]

        if 'sw_lat' in parsed_qs:
            params['sw_lat'] = parsed_qs['sw_lat'][0]

        if 'sw_lng' in parsed_qs:
            params['sw_lng'] = parsed_qs['sw_lng'][0]


class AirbnbCalendarScraper(AirbnbScraperInterface):
    def __init__(self, calendar: Calendar, persistence: PersistenceInterface, logger: Logger):
        self.__calendar = calendar
        self.__logger = logger
        self.__persistence = persistence

    def run(self, source: str):
        if source == 'elasticsearch':
            assert isinstance(self.__persistence, Elastic)
            for listing_id in self.__persistence.get_all_index_ids():
                try:
                    self.__calendar.get_calendar(listing_id=listing_id)
                except ForbiddenException:
                    if self.__exists_listing(listing_id):
                        raise RuntimeError('Could not get listing calendar for %s' % listing_id)
                    else:
                        self.__logger.warning('GONE: deleting listing id {}'.format(listing_id))
                        self.__persistence.mark_deleted(listing_id)
        else:  # it's a listing id
            self.__calendar.get_calendar(listing_id=source)

    @staticmethod
    def __exists_listing(listing_id):
        # check if listing still exists
        url = BaseEndpoint.build_airbnb_url('/rooms/{}'.format(listing_id))
        response = requests.get(url)

        if response.status_code == 200:  # OK
            return True
        elif response.status_code == 410:  # Gone
            return False
        else:
            raise RuntimeError('Unhandled response code: {}\n{}'.format(response.status_code, response.json()))
