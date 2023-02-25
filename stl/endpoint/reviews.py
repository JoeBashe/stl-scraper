import json
import requests

from stl.endpoint.base_endpoint import BaseEndpoint


class Reviews(BaseEndpoint):
    API_PATH = '/api/v3/PdpReviews'

    def get_reviews(self, listing_id: str, limit: int = 50, start_offset: int = 0):
        """Perform API request."""
        # get first batch of reviews
        reviews, n_reviews_total = self.__get_reviews_batch(listing_id, limit, start_offset)

        # get any additional batches
        start_idx = start_offset + limit
        for offset in range(start_idx, n_reviews_total, limit):
            r, _ = self.__get_reviews_batch(listing_id, limit, offset)
            reviews.extend(r)

        return reviews

    def __get_reviews_batch(self, listing_id: str, limit: int, offset: int):
        """Get reviews for a given listing ID in batches."""
        url = self.__get_url(listing_id, limit, offset)
        headers = {'x-airbnb-api-key': self._api_key}
        response = requests.get(url, headers=headers)
        data = json.loads(response.text)
        pdp_reviews = data['data']['merlin']['pdpReviews']
        if isinstance(pdp_reviews, dict):
            n_reviews_total = (
                int(pdp_reviews['metadata']['reviewsCount'])
            ) if pdp_reviews.get('metadata') else len(pdp_reviews['reviews'])
        else:
            n_reviews_total = 0

        reviews = [{
            'comments':   r['comments'],
            'created_at': r['createdAt'],
            'language':   r['language'],
            'rating':     r['rating'],
            'response':   r['response'],
        } for r in pdp_reviews['reviews']]

        return reviews, n_reviews_total

    def __get_url(self, listing_id: str, limit: int = 7, offset: int = None) -> str:
        query = {
            'operationName': 'PdpReviews',
            'locale':        self._locale,
            'currency':      self._currency,
            'variables':     {
                'request': {
                    'fieldSelector':    'for_p3',
                    'limit':            limit,
                    'listingId':        listing_id,
                    'numberOfAdults':   '1',
                    'numberOfChildren': '0',
                    'numberOfInfants':  '0'
                }
            },
            'extensions':    {
                'persistedQuery': {
                    'version':    1,
                    'sha256Hash': '4730a25512c4955aa741389d8df80ff1e57e516c469d2b91952636baf6eee3bd'
                }
            }
        }

        if offset:
            query['variables']['request']['offset'] = offset

        self._put_json_param_strings(query)

        return BaseEndpoint.build_airbnb_url(self.API_PATH, query)
