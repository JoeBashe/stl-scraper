from stl.endpoint.base_endpoint import BaseEndpoint


class Explore(BaseEndpoint):
    API_PATH = '/api/v3/ExploreSearch'

    def get_url(self, search_string: str, params: dict = None):
        query = {
            'operationName': 'ExploreSearch',
            'locale':        self._locale,
            'currency':      self._currency,
            '_cb':           'ld7rar1fhh6if',
        }
        data = {
            'variables':  {
                'request': {
                    'metadataOnly':          False,
                    'version':               '1.7.9',
                    'itemsPerGrid':          20,
                    'tabId':                 'home_tab',
                    'refinementPaths':       ['/homes'],
                    'source':                'structured_search_input_header',
                    'searchType':            'filter_change',
                    'query':                 search_string,
                    'cdnCacheSafe':          False,
                    'simpleSearchTreatment': 'simple_search_only',
                    'treatmentFlags':        [
                        'simple_search_1_1',
                        'simple_search_desktop_v3_full_bleed',
                        'flexible_dates_options_extend_one_three_seven_days'
                    ],
                    'screenSize':            'large'
                }
            },
            'extensions': {
                'persistedQuery': {
                    'version':    1,
                    'sha256Hash': '13aa9971e70fbf5ab888f2a851c765ea098d8ae68c81e1f4ce06e2046d91b6ea'
                }
            }
        }
        if params:
            data['variables']['request'] |= params

        self._put_json_param_strings(data)

        url = BaseEndpoint.build_airbnb_url(self.API_PATH, query)
        url += '&variables=%s' % data['variables']
        url += '&extensions=%s' % data['extensions']

        return url

    def search(self, url: str):
        data = self._api_request(url)
        pagination = data['data']['dora']['exploreV3']['metadata']['paginationMetadata']

        return data, pagination
