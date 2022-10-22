import logging
import os.path
import sys

from configparser import ConfigParser
from elasticsearch import Elasticsearch

from stl.endpoint.explore import Explore
from stl.endpoint.pdp import Pdp
from stl.endpoint.reviews import Reviews
from stl.persistence.csv import Csv
from stl.persistence.elastic import Elastic
from stl.scraper.airbnb_scraper import AirbnbScraper


class StlCommand:
    """Short-Term Listings (STL) Scraper

Usage:
    stl.py <query> [--currency=<currency>] [--roomTypes=<roomTypes>]

Arguments:
    <query>     - The query string to search (e.g. "San Diego, CA").
    <currency>  - USD (default), EUR, etc.
    <roomTypes> - e.g. "Entire home/apt". Can include multiple separated by comma.
"""

    @staticmethod
    def execute(args):
        # get config
        project_path = os.path.dirname(os.path.realpath('{}/../../'.format(__file__)))
        config = StlCommand.__config(project_path)

        # create scraper
        stl = StlCommand.__create_scraper(args, config, project_path)

        # run scraper
        params = StlCommand.__get_search_params(args, config)
        query = args['<query>']
        stl.run(query, params)

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
    def __create_scraper(args: dict, config: ConfigParser, project_path: str):
        # get endpoints
        api_key = config['airbnb']['api_key']
        currency = args.get('--currency', 'USD')
        explore = Explore(api_key, currency)
        pdp = Pdp(api_key, currency)
        reviews = Reviews(api_key, currency)

        # load persistence layer
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
        return AirbnbScraper(explore, pdp, reviews, persistence, logging.getLogger(__class__.__module__.lower()))

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
