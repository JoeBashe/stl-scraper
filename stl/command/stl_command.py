import logging
import os.path
import sys

from configparser import ConfigParser
from elasticsearch import Elasticsearch

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
    stl.py search <query> [--currency=<currency>] [--roomTypes=<roomTypes>]
    stl.py calendar <source>
    stl.py data <listingId>
    stl.py pricing <listingId> <checkin> <checkout>

Arguments:
    <query>     - The query string to search (e.g. "San Diego, CA").
    <currency>  - USD (default), EUR, etc.
    <listingId> - The Listing ID
    <roomTypes> - e.g. "Entire home/apt". Can include multiple separated by comma.
    <source>    - One of either: a. Listing ID; or b. the special keyword "elasticsearch".
"""

    @staticmethod
    def execute(args: dict):
        # get config
        project_path = os.path.dirname(os.path.realpath('{}/../../'.format(__file__)))
        config = StlCommand.__config(project_path)
        currency = args.get('--currency') or 'USD'
        if args.get('search'):
            query = args['<query>']
            persistence = StlCommand.__create_persistence(config, project_path, query)
            scraper = StlCommand.__create_scraper('search', persistence,  config, currency)
            params = StlCommand.__get_search_params(args, config)
            scraper.run(query, params)
        elif args.get('calendar'):
            persistence = StlCommand.__create_persistence(config, project_path)
            scraper = StlCommand.__create_scraper('calendar', persistence, config, currency)
            source = args['<source>']
            scraper.run(source)
        elif args.get('data'):
            api_key = config['airbnb']['api_key']
            pdp = Pdp(api_key, currency)
            print(pdp.get_raw_listing(args.get('<listingId>')))
        elif args.get('pricing'):
            listing_id = args.get('<listingId>')
            checkin = args.get('<checkin>')
            checkout = args.get('<checkout>')
            pricing = Pricing(config['airbnb']['api_key'], currency)
            total = pricing.get_pricing(checkin, config, listing_id)
            print('https://www.airbnb.com/rooms/{} - {} to {}: {}'.format(listing_id, checkin, checkout, total))
        else:
            raise RuntimeError('ERROR: Unexpected command:\n{}'.format(*args))

    @staticmethod
    def __config(project_path: str) -> ConfigParser:
        """Config logger, then load and return app config from stl.ini config file."""
        # config logger
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(message)s",
            handlers=[logging.StreamHandler(sys.stdout)]
        )

        # get app config
        config = ConfigParser()
        config.read(os.path.join(project_path, 'stl.ini'))

        return config

    @staticmethod
    def __create_scraper(
            scraper_type: str,
            persistence: PersistenceInterface,
            config: ConfigParser,
            currency: str,
    ) -> AirbnbScraperInterface:
        # create scraper
        api_key = config['airbnb']['api_key']
        logger = logging.getLogger(__class__.__module__.lower())
        if scraper_type == 'search':
            explore = Explore(api_key, currency)
            pdp = Pdp(api_key, currency)
            reviews = Reviews(api_key, currency)
            return AirbnbSearchScraper(explore, pdp, reviews, persistence, logger)
        elif scraper_type == 'calendar':
            pricing = Pricing(api_key, currency)
            calendar = Calendar(api_key, currency, pricing)
            return AirbnbCalendarScraper(calendar, persistence, logger)
        else:
            raise RuntimeError('Unknown scraper type: %s' % scraper_type)

    @staticmethod
    def __create_persistence(config: ConfigParser, project_path: str = None, query: str = None):
        # config persistence layer
        storage_type = config['storage']['type']
        if storage_type == 'elasticsearch':
            es_cfg = config['elasticsearch']
            persistence = Elastic(
                Elasticsearch(hosts=es_cfg['hosts'], basic_auth=(es_cfg['username'], es_cfg['password'])),
                config['elasticsearch']['index']
            )
            persistence.create_index_if_not_exists(config['elasticsearch']['index'])
        else:
            csv_path = os.path.join(project_path, '{}.csv'.format(query))
            persistence = Csv(csv_path)

        return persistence

    @staticmethod
    def __get_search_params(args, config):
        params = {}
        room_types = StlCommand.__get_list_arg(args, config, 'roomTypes')
        if room_types:
            params['roomTypes'] = room_types

        return params

    @staticmethod
    def __get_list_arg(args: dict, config: ConfigParser, arg_name: str):
        """Get CLI comma-separated list argument, fall back to config."""
        return list(filter(bool, map(
            str.strip, str(args.get('--{}'.format(arg_name), config['search'].get(arg_name, ''))).split(','))))
