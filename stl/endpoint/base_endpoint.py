import json
import requests

from abc import ABC
from logging import Logger
from random import randint
from time import sleep
from urllib.parse import urlunparse, urlencode

from stl.exception.api import ApiException, ForbiddenException

import urllib3
urllib3.disable_warnings()


class BaseEndpoint(ABC):
    API_PATH = None
    SOURCE = 'airbnb'

    def __init__(self, api_key: str, currency: str, proxy: str, ignore_cert: bool, throttle:bool, logger: Logger, locale: str = 'en'):
        self._api_key = api_key
        self._currency = currency
        self._locale = locale
        self._logger = logger
        self._proxy = {'http': proxy,
                      'https': proxy}
        self._throttle=throttle
        self._verify_cert = not ignore_cert

    @staticmethod
    def build_airbnb_url(path: str, query=None):
        if query is not None:
            query = urlencode(query)

        return urlunparse(['https', 'www.airbnb.com', path, None, query, None])

    def _api_request(self, url: str, method: str = 'GET', data=None) -> dict:
        if data is None:
            data = {}

        attempts = 0
        headers = {'x-airbnb-api-key': self._api_key}
        max_attempts = 3
        while attempts < max_attempts:
            if self._throttle:
                sleep(randint(0, 2))  # do a little throttling
            attempts += 1
            response = requests.request(method, url, headers=headers, data=data, proxies=self._proxy, verify=self._verify_cert)
            response_json = response.json()
            errors = response_json.get('errors')
            if not errors:
                return response_json

            self.__handle_api_error(url, errors)

        raise ApiException(['Could not complete API {} request to "{}"'.format(method, url)])

    @staticmethod
    def _put_json_param_strings(query: dict):
        """Property format JSON strings for 'variables' & 'extensions' params."""
        query['variables'] = json.dumps(query['variables'], separators=(',', ':'))
        query['extensions'] = json.dumps(query['extensions'], separators=(',', ':'))

    def __handle_api_error(self, url: str, errors: list):
        error = errors.pop()
        if isinstance(error, dict):
            if error.get('extensions'):
                if error['extensions'].get('response'):
                    status_code = error['extensions']['response'].get('statusCode')
                    if status_code == 403:
                        self._logger.critical('403 Forbidden: %s' % url)
                        raise ForbiddenException([error])
                    if status_code >= 500:
                        sleep(60)  # sleep for a minute and then make another attempt
                        self._logger.warning(error)
                        return
                elif error['extensions'].get('classification') == 'DataFetchingException':
                    sleep(60)  # sleep for a minute and then make another attempt
                    self._logger.warning(error['message'])
                    return

            if 'please try again' in error['message'].lower():
                sleep(30)  # sleep 30 seconds then make another attempt
                self._logger.warning(error['message'])
                return

        raise ApiException(errors)
