import logging
import os.path
import sys

from configparser import ConfigParser
from elasticsearch import Elasticsearch

from stl.endpoint.Explore import Explore
from stl.endpoint.Pdp import Pdp
from stl.endpoint.Reviews import Reviews
from stl.persistence.Csv import Csv
from stl.persistence.Elastic import Elastic
from stl.scraper.AirbnbScraper import AirbnbScraper


class StlCommand:
    """Short-Term Listings (STL) Scraper

Usage:
    stl.py <query> [--currency=<currency>]

Arguments:
    <query> - The query string to search (e.g. "San Diego, CA")
    <currency> - USD (default), EUR, etc..
"""

    @staticmethod
    def execute(args):
        # create scraper
        stl = StlCommand.__create_scraper(args)

        # run scraper
        query = args['<query>']
        stl.run(query)

    @staticmethod
    def __create_scraper(args):
        project_path = os.path.dirname(os.path.realpath('{}/../../'.format(__file__)))

        # get config
        config = StlCommand.__config(project_path)

        # get endpoints
        api_key = config['airbnb']['api_key']
        currency = args.get('--currency', 'USD')
        explore = Explore(api_key, currency)
        pdp = Pdp(api_key, currency)
        reviews = Reviews(api_key, currency)

        # load persistence layer
        storage_type = config['main']['storage_type']
        if storage_type == 'elasticsearch':
            es_cfg = config['elasticsearch']
            persistence = Elastic(
                Elasticsearch(hosts=es_cfg['hosts'], basic_auth=(es_cfg['username'], es_cfg['password'])),
                config['elasticsearch']['index'])
            persistence.create_index_if_not_exists(config['elasticsearch']['index'])
        else:
            persistence = Csv(project_path)

        # create scraper
        return AirbnbScraper(explore, pdp, reviews, persistence, logging.getLogger(__class__.__module__.lower()))

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
