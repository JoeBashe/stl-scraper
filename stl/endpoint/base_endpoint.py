import json
import requests

from abc import ABC
from urllib.parse import urlunparse, urlencode


class BaseEndpoint(ABC):
    def __init__(self, api_key: str, currency: str, locale: str = 'en'):
        self._api_key = api_key
        self._currency = currency
        self._locale = locale

    def _api_request(self, url: str, method: str = 'GET', data=None) -> dict:
        if data is None:
            data = {}
        headers = {'x-airbnb-api-key': self._api_key}
        response = requests.request(method, url, headers=headers, data=data)
        return response.json()

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
