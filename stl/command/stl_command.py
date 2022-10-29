import logging
import os.path
import sys

from configparser import ConfigParser
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
    --updated=<updated>    Only update listings not updated in given period [default: 1d]
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
            format="%(asctime)s [%(levelname)s] %(message)s",
            handlers=[logging.StreamHandler(sys.stdout)]
        )
        return logging.getLogger(__class__.__module__.lower())

    def execute(self):
        project_path = os.path.dirname(os.path.realpath('{}/../../'.format(__file__)))
        config = StlCommand.__config(project_path)
        currency = self.__args.get('--currency') or config['search'].get('currency', 'USD')
        if self.__args.get('search'):
            query = self.__args['<query>']
            persistence = self.__create_persistence(config, project_path, query)
            scraper = self.__create_scraper('search', persistence, config, currency)
            params = self.__get_search_params(config)
            scraper.run(query, params)

        elif self.__args.get('calendar'):
            if self.__args.get('--all') and self.__args.get('--storage') == 'csv':
                self.__logger.critical('"csv" storage backend not supported in combination with "--all" option.')
                exit(1)
            persistence = self.__create_persistence(config, project_path)
            scraper = self.__create_scraper('calendar', persistence, config, currency)
            source = 'elasticsearch' if self.__args.get('--all') else self.__args['<listingId>']
            scraper.run(source, self.__args.get('--updated'))

        elif self.__args.get('data'):
            api_key = config['airbnb']['api_key']
            pdp = Pdp(api_key, currency, self.__logger)
            print(pdp.get_raw_listing(self.__args.get('<listingId>')))

        elif self.__args.get('pricing'):
            listing_id = self.__args.get('<listingId>')
            checkin = self.__args.get('<checkin>')
            checkout = self.__args.get('<checkout>')
            pricing = Pricing(config['airbnb']['api_key'], currency, self.__logger)
            total = pricing.get_pricing(checkin, config, listing_id)
            print('https://www.airbnb.com/rooms/{} - {} to {}: {}'.format(listing_id, checkin, checkout, total))

        else:
            raise RuntimeError('ERROR: Unexpected command:\n{}'.format(*self.__args))

    @staticmethod
    def __config(project_path: str) -> ConfigParser:
        """Config logger, then load and return app config from stl.ini config file."""
        config = ConfigParser()
        config.read(os.path.join(project_path, 'stl.ini'))
        return config

    def __create_scraper(
            self,
            scraper_type: str,
            persistence: PersistenceInterface,
            config: ConfigParser,
            currency: str
    ) -> AirbnbScraperInterface:
        """Create scraper of given type using given parameters."""
        api_key = config['airbnb']['api_key']
        if scraper_type == 'search':
            explore = Explore(api_key, currency, self.__logger)
            pdp = Pdp(api_key, currency, self.__logger)
            reviews = Reviews(api_key, currency, self.__logger)
            return AirbnbSearchScraper(explore, pdp, reviews, persistence, self.__logger)
        elif scraper_type == 'calendar':
            pricing = Pricing(api_key, currency, self.__logger)
            calendar = Calendar(api_key, currency, self.__logger, pricing)
            return AirbnbCalendarScraper(calendar, persistence, self.__logger)
        else:
            raise RuntimeError('Unknown scraper type: %s' % scraper_type)

    def __create_persistence(
            self, config: ConfigParser, project_path: str = None, query: str = None) -> PersistenceInterface:
        """Create persistence layer - either CSV or Elasticsearch."""
        storage_type = self.__args.get('--storage') or config['storage']['type']
        if storage_type == 'elasticsearch':
            es_cfg = config['elasticsearch']
            persistence = Elastic(
                Elasticsearch(hosts=es_cfg['hosts'], basic_auth=(es_cfg['username'], es_cfg['password'])),
                config['elasticsearch']['index']
            )
            try:
                persistence.create_index_if_not_exists(config['elasticsearch']['index'])
            except ConnectionError as e:
                self.__logger.critical(e.message + '\nCould not connect to elasticsearch.')
                exit(1)
        else:
            csv_path = os.path.join(project_path, '{}.csv'.format(query))
            persistence = Csv(csv_path)

        return persistence

    def __get_search_params(self, config: ConfigParser) -> dict:
        """Get search parameters: roomTypes,."""
        params = {}
        room_types = self.__get_list_arg(config, 'roomTypes')
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

    def __get_list_arg(self, config: ConfigParser, arg_name: str) -> list | None:
        """Get CLI comma-separated list argument, fall back to config."""
        arg_val = self.__args.get('--{}'.format(arg_name)) or config['search'].get(arg_name, '')
        if not arg_val:
            return None
        return list(filter(bool, map(str.strip, str(arg_val).split(','))))
