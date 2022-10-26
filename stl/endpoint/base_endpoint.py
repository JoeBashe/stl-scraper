import json
import requests

from abc import ABC
from time import sleep
from urllib.parse import urlunparse, urlencode

from stl.exception.api import ApiException, ForbiddenException, ServerException


class BaseEndpoint(ABC):
    def __init__(self, api_key: str, currency: str, locale: str = 'en'):
        self._api_key = api_key
        self._currency = currency
        self._locale = locale

    def _api_request(self, url: str, method: str = 'GET', data=None) -> dict:
        if data is None:
            data = {}

        attempts = 0
        headers = {'x-airbnb-api-key': self._api_key}
        max_attempts = 3
        while attempts < max_attempts:
            attempts += 1
            response = requests.request(method, url, headers=headers, data=data)
            response_json = response.json()
            errors = response_json.get('errors')
            if not errors:
                return response_json

            self.__handle_api_error(errors)

        raise ApiException(['Could not complete API {} request to "{}"'.format(method, url)])

    @staticmethod
    def build_airbnb_url(path: str, query=None):
        if query is not None:
            query = urlencode(query)

        return urlunparse(['https', 'www.airbnb.com', path, None, query, None])

    @staticmethod
    def _put_json_param_strings(query: dict):
        """Property format JSON strings for 'variables' & 'extensions' params."""
        query['variables'] = json.dumps(query['variables'], separators=(',', ':'))
        query['extensions'] = json.dumps(query['extensions'], separators=(',', ':'))

    @staticmethod
    def __handle_api_error(errors: list):
        error = errors.pop()
        if isinstance(error, dict) and error.get('extensions') and error['extensions'].get('response'):
            status_code = error['extensions']['response'].get('statusCode')
            if status_code == 403:
                raise ForbiddenException([error])
            if status_code >= 500:
                sleep(60)  # sleep for a minute and then make another attempt
                return

        raise ApiException(errors)
