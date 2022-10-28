import json
import requests

from abc import ABC
from logging import Logger
from random import randint
from time import sleep
from urllib.parse import urlunparse, urlencode

from stl.exception.api import ApiException, ForbiddenException


class BaseEndpoint(ABC):
    API_PATH = None
    SOURCE = 'airbnb'

    def __init__(self, api_key: str, currency: str, logger: Logger, locale: str = 'en'):
        self._api_key = api_key
        self._currency = currency
        self._locale = locale
        self._logger = logger

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
            sleep(randint(0, 2))  # do a little throttling
            attempts += 1
            response = requests.request(method, url, headers=headers, data=data)
            response_json = response.json()
            errors = response_json.get('errors')
            if not errors:
                return response_json

            self.__handle_api_error(errors)

        raise ApiException(['Could not complete API {} request to "{}"'.format(method, url)])

    @staticmethod
    def _put_json_param_strings(query: dict):
        """Property format JSON strings for 'variables' & 'extensions' params."""
        query['variables'] = json.dumps(query['variables'], separators=(',', ':'))
        query['extensions'] = json.dumps(query['extensions'], separators=(',', ':'))

    def __handle_api_error(self, errors: list):
        error = errors.pop()
        if isinstance(error, dict) and error.get('extensions'):
            if error['extensions'].get('response'):
                status_code = error['extensions']['response'].get('statusCode')
                if status_code == 403:
                    raise ForbiddenException([error])
                if status_code >= 500:
                    sleep(60)  # sleep for a minute and then make another attempt
                    self._logger.warning(error)
                    return
            elif error['extensions'].get('classification') == 'DataFetchingException':
                sleep(60)  # sleep for a minute and then make another attempt
                self._logger.warning(error['message'])
                return

        raise ApiException(errors)
