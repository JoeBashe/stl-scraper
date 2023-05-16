import json
import logging
import os
import sys

from elasticsearch import Elasticsearch
from elastic_transport import ConnectionError
from logging import Logger

from stl.endpoint.calendar import Calendar, Pricing
from stl.endpoint.explore import Explore
from stl.endpoint.pdp import Pdp
from stl.endpoint.reviews import Reviews
from stl.persistence.csv import Csv
from stl.persistence.elastic import Elastic
from stl.persistence import PersistenceInterface
from stl.scraper.airbnb_scraper import AirbnbSearchScraper, AirbnbCalendarScraper, AirbnbScraperInterface


class StlCommand:
    """Short-Term Listings (STL) Scraper

Usage:
    stl.py search <query> [--checkin=<checkin> --checkout=<checkout> [--priceMin=<priceMin>] [--priceMax=<priceMax>]] \
[--roomTypes=<roomTypes>] [--storage=<storage>] [-v|--verbose]
    stl.py calendar (<listingId> | --all) [--updated=<updated>]
    stl.py pricing <listingId> --checkin=<checkin> --checkout=<checkout>
    stl.py data <listingId>

Arguments:
    <query>          The query string to search (e.g. "San Diego, CA")
    <listingId>      The listing id

Options:
    --checkin=<checkin>    Check-in date, e.g. "2023-06-01"
    --checkout=<checkout>  Check-out date, e.g. "2023-06-30"
    --priceMin=<priceMin>  Minimum nightly or monthly price
    --priceMax=<priceMax>  Maximum nightly or monthly price
    --updated=<updated>    Only update listings not updated in given period. Prevents updating listings that have been \
recently updated. [default: 1d]
    --all                  Update calendar for all listings (requires Elasticsearch backend)

Global Options:
    --currency=<currency>  "USD", "EUR", etc. (default: USD)
    --source=<source>      Only allows "airbnb" [default: airbnb]
    --storage=<storage>    csv or elasticsearch (default: csv)
    -v, --verbose          Verbose logging output
"""

    def __init__(self, args: dict):
        self.__args = args
        self.__logger = StlCommand.__get_logger(bool(args.get('--verbose')))

    @staticmethod
    def __get_logger(is_verbose: bool) -> Logger:
        """Configure and get logger instance."""
        logging.basicConfig(
            level=logging.INFO if is_verbose else logging.WARNING,
            format='%(asctime)s [%(levelname)s] %(message)s',
            handlers=[logging.StreamHandler(sys.stdout)]
        )
        return logging.getLogger(__class__.__module__.lower())

    def execute(self):
        project_path = os.path.dirname(os.path.realpath('{}/../../'.format(__file__)))
        currency = self.__args.get('--currency') or os.getenv('SEARCH_CURRENCY', 'USD')
        if self.__args.get('search'):
            query = self.__args['<query>']
            persistence = self.__create_persistence(project_path, query)
            scraper = self.__create_scraper('search', persistence, currency)
            params = self.__get_search_params()
            scraper.run(query, params)

        elif self.__args.get('calendar'):
            if self.__args.get('--all') and self.__args.get('--storage') == 'csv':
                self.__logger.critical('"csv" storage backend not supported in combination with "--all" option.')
                exit(1)
            persistence = self.__create_persistence(project_path)
            scraper = self.__create_scraper('calendar', persistence, currency)
            source = 'elasticsearch' if self.__args.get('--all') else self.__args['<listingId>']
            scraper.run(source, self.__args.get('--updated'))

        elif self.__args.get('data'):
            ca_cert = os.getenv('CA_CERT', None)
            throttle = int(os.getenv('THROTTLE', 2))
            pdp = Pdp(os.getenv('AIRBNB_API_KEY'), currency, os.getenv('PROXY', None), ca_cert, throttle, self.__logger)
            print(json.dumps(pdp.get_raw_listing(self.__args.get('<listingId>'))))

        elif self.__args.get('pricing'):
            listing_id = self.__args.get('<listingId>')
            checkin = self.__args.get('--checkin')
            checkout = self.__args.get('--checkout')
            ca_cert = os.getenv('CA_CERT', None)
            throttle = int(os.getenv('THROTTLE', 2))
            pricing = Pricing(os.getenv('AIRBNB_API_KEY'), currency, os.getenv('PROXY', None), ca_cert, throttle, self.__logger)
            total = pricing.get_pricing(checkin, checkout, listing_id)
            print('https://www.airbnb.com/rooms/{} - {} to {}: {}'.format(listing_id, checkin, checkout, total))

        else:
            raise RuntimeError('ERROR: Unexpected command:\n{}'.format(*self.__args))

    def __create_scraper(
            self,
            scraper_type: str,
            persistence: PersistenceInterface,
            currency: str
    ) -> AirbnbScraperInterface:
        """Create scraper of given type using given parameters."""
        api_key = os.getenv('AIRBNB_API_KEY')
        proxy = os.getenv('PROXY', None)
        ca_cert = os.getenv('CA_CERT', None)

        throttle = int(os.getenv('THROTTLE', 2))
        if scraper_type == 'search':
            explore = Explore(api_key, currency, proxy, ca_cert, throttle, self.__logger)
            pdp = Pdp(api_key, currency, proxy, ca_cert, throttle, self.__logger)
            reviews = Reviews(api_key, currency, proxy, ca_cert, throttle, self.__logger)
            return AirbnbSearchScraper(explore, pdp, reviews, persistence,currency, self.__logger)
        elif scraper_type == 'calendar':
            pricing = Pricing(api_key, currency, proxy, ca_cert, throttle, self.__logger)
            calendar = Calendar(api_key, currency, proxy, ca_cert, throttle, self.__logger, pricing)
            return AirbnbCalendarScraper(calendar, persistence, self.__logger)
        else:
            raise RuntimeError('Unknown scraper type: %s' % scraper_type)

    def __create_persistence(self, project_path: str = None, query: str = None) -> PersistenceInterface:
        """Create persistence layer - either CSV or Elasticsearch."""
        storage_type = self.__args.get('--storage') or os.getenv('STORAGE_TYPE')
        if storage_type == 'elasticsearch':
            es_params = {
                'hosts':      os.getenv('ELASTIC_HOSTS'),
                'basic_auth': (os.getenv('ELASTIC_USERNAME'), os.getenv('ELASTIC_PASSWORD')),
            }
            if os.getenv('ELASTIC_CA_CERT'):
                es_params['ca_certs'] = os.getenv('ELASTIC_CA_CERT')
            else:
                es_params['verify_certs'] = False
            persistence = Elastic(Elasticsearch(**es_params), os.getenv('ELASTIC_INDEX'))
            try:
                persistence.create_index_if_not_exists(os.getenv('ELASTIC_INDEX'))
            except ConnectionError as e:
                self.__logger.critical(e.message + '\nCould not connect to elasticsearch.')
                exit(1)
        else:  # assume csv
            csv_path = os.path.join(project_path, '{}.csv'.format(query))
            persistence = Csv(csv_path)

        return persistence

    def __get_search_params(self) -> dict:
        """Get search parameters: roomTypes, checkin, checkout, priceMin, priceMax."""
        params = {}
        room_types = self.__get_list_arg('roomTypes')
        if room_types:
            params['roomTypes'] = room_types

        if self.__args.get('--checkin'):
            params['checkin'] = self.__args['--checkin']
            params['checkout'] = self.__args['--checkout']

        if self.__args.get('--priceMax'):
            params['priceMax'] = self.__args['--priceMax']

        if self.__args.get('--priceMin'):
            params['priceMin'] = self.__args['--priceMin']

        return params

    def __get_list_arg(self, arg_name: str) -> list | None:
        """Get CLI comma-separated list argument, fall back to config."""
        arg_val = self.__args.get('--{}'.format(arg_name)) or os.getenv('SEARCH_{}'.format(arg_name.upper()), '')
        if not arg_val:
            return None

        return list(filter(bool, map(str.strip, str(arg_val).split(','))))
