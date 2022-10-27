import logging
import os.path
import sys

from configparser import ConfigParser
from elasticsearch import Elasticsearch
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
    stl.py search <query> [--currency=<currency>] [--roomTypes=<roomTypes>] [--source=<source>]
    stl.py calendar <listingSource> [--currency=<currency>] [--source=<source>]
    stl.py pricing <listingId> <checkin> <checkout> [--currency=<currency>] [--source=<source>]
    stl.py data <listingId> [--source=<source>]

Arguments:
    <query>         - The query string to search (e.g. "San Diego, CA").
    <currency>      - "USD", "EUR", etc. (default: USD)
    <listingId>     - The listing id.
    <roomTypes>     - e.g. "Entire home/apt". Can include multiple separated by comma.
    <listingSource> - One of either: a. listing ID; or b. the special keyword "elasticsearch".
    <source>        - Only allows "airbnb" for now. (default: "airbnb")
"""

    @staticmethod
    def execute(args: dict):
        logger = logging.getLogger(__class__.__module__.lower())
        project_path = os.path.dirname(os.path.realpath('{}/../../'.format(__file__)))
        config = StlCommand.__config(project_path)
        currency = args.get('--currency') or config['search'].get('currency', 'USD')
        if args.get('search'):
            query = args['<query>']
            persistence = StlCommand.__create_persistence(config, project_path, query)
            scraper = StlCommand.__create_scraper('search', persistence, config, currency, logger)
            params = StlCommand.__get_search_params(args, config)
            scraper.run(query, params)
        elif args.get('calendar'):
            persistence = StlCommand.__create_persistence(config, project_path)
            scraper = StlCommand.__create_scraper('calendar', persistence, config, currency, logger)
            source = args['<source>']
            scraper.run(source)
        elif args.get('data'):
            api_key = config['airbnb']['api_key']
            pdp = Pdp(api_key, currency, logger)
            print(pdp.get_raw_listing(args.get('<listingId>')))
        elif args.get('pricing'):
            listing_id = args.get('<listingId>')
            checkin = args.get('<checkin>')
            checkout = args.get('<checkout>')
            pricing = Pricing(config['airbnb']['api_key'], currency, logger)
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
            logger: Logger
    ) -> AirbnbScraperInterface:
        # create scraper
        api_key = config['airbnb']['api_key']
        if scraper_type == 'search':
            explore = Explore(api_key, currency, logger)
            pdp = Pdp(api_key, currency, logger)
            reviews = Reviews(api_key, currency, logger)
            return AirbnbSearchScraper(explore, pdp, reviews, persistence, logger)
        elif scraper_type == 'calendar':
            pricing = Pricing(api_key, currency, logger)
            calendar = Calendar(api_key, currency, logger, pricing)
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
