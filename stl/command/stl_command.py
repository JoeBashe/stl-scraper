import json
import logging
import os.path
import sys

from configparser import ConfigParser
from elasticsearch import Elasticsearch

from stl.endpoint.calendar import Calendar, StartStaysCheckout
from stl.endpoint.explore import Explore
from stl.endpoint.pdp import Pdp
from stl.endpoint.reviews import Reviews
from stl.persistence.csv import Csv
from stl.persistence.elastic import Elastic
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
    <source>    - One of either: a) Listing ID; or b) the special keyword "elasticsearch".
"""

    @staticmethod
    def execute(args):
        # get config
        project_path = os.path.dirname(os.path.realpath('{}/../../'.format(__file__)))
        config = StlCommand.__config(project_path)
        if args.get('search'):
            # create scraper
            scraper = StlCommand.__create_scraper('search', args, config, project_path)
            params = StlCommand.__get_search_params(args, config)
            query = args['<query>']
            # run scraper
            scraper.run(query, params)
        elif args.get('calendar'):
            # create scraper
            scraper = StlCommand.__create_scraper('calendar', args, config, project_path)
            source = args['<source>']
            scraper.run(source)
        elif args.get('data'):
            api_key = config['airbnb']['api_key']
            currency = args.get('--currency', 'USD')
            pdp = Pdp(api_key, currency)
            print(pdp.get_raw_listing(args.get('<listingId>')))
        elif args.get('pricing'):
            api_key = config['airbnb']['api_key']
            currency = args.get('--currency', 'USD')
            pricing = StartStaysCheckout(api_key, currency)
            rates = pricing.get_rates(args.get('<listingId>'), args.get('<checkin>'), args.get('<checkout>'))
            sections = rates['data']['startStayCheckoutFlow']['stayCheckout']['sections']
            quickpay_data = json.loads(sections['temporaryQuickPayData']['bootstrapPaymentsJSON'])
            print(rates)
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
            scraper_type: str, args: dict, config: ConfigParser, project_path: str) -> AirbnbScraperInterface:
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
            persistence = Csv(project_path)

        # create scraper
        api_key = config['airbnb']['api_key']
        currency = args.get('--currency', 'USD')
        logger = logging.getLogger(__class__.__module__.lower())
        if scraper_type == 'search':
            explore = Explore(api_key, currency)
            pdp = Pdp(api_key, currency)
            reviews = Reviews(api_key, currency)
            return AirbnbSearchScraper(explore, pdp, reviews, persistence, logger)
        else:  # assume 'calendar'
            calendar = Calendar(api_key, currency)
            pricing = StartStaysCheckout(api_key, currency)
            return AirbnbCalendarScraper(calendar, pricing, persistence, logger)

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
