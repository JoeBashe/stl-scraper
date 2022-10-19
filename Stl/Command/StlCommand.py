import logging
import os.path
import sys

from configparser import ConfigParser

from Stl.Endpoint.Explore import Explore
from Stl.Endpoint.Pdp import Pdp
from Stl.Endpoint.Reviews import Reviews
from Stl.Scraper.AirbnbScraper import AirbnbScraper


class StlCommand:
    """Short-Term Listings (STL) Scraper

Usage:
    stl.py <query>

Arguments:
    <query> - The query string to search (e.g. "San Diego, CA")
"""

    @staticmethod
    def execute(args):
        # get config
        config = StlCommand.__get_config()
        # config logger
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(message)s",
            handlers=[logging.StreamHandler(sys.stdout)]
        )
        # get endpoints
        api_key = config['main']['api_key']
        currency = args.get('--currency', 'USD')
        explore = Explore(api_key, currency)
        pdp = Pdp(api_key, currency)
        reviews = Reviews(api_key, currency)
        # run scraper
        stl = AirbnbScraper(explore, pdp, reviews, logging.getLogger(__class__.__module__.lower()))
        query = args['<query>']
        stl.run(query)

    @staticmethod
    def __get_config():
        config = ConfigParser()
        config_path = os.path.dirname(os.path.realpath('{}/../../'.format(__file__)))
        config.read(os.path.join(config_path, 'stl.ini'))
        return config
