import json
import requests

from abc import ABC
from urllib.parse import urlunparse, urlencode


class BaseEndpoint(ABC):
    def __init__(self, api_key: str, currency: str):
        self._api_key = api_key
        self._currency = currency

    def _api_request(self, url: str) -> dict:
        headers = {'x-airbnb-api-key': self._api_key}
        response = requests.request('GET', url, headers=headers, data={})
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
