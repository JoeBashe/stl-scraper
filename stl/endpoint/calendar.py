import json

from datetime import datetime

from stl.endpoint.base_endpoint import BaseEndpoint


class Calendar(BaseEndpoint):
    N_MONTHS = 12  # number of months of data to return; 12 months == 1 year

    def __init__(self, api_key: str, currency: str):
        super().__init__(api_key, currency)
        self.__today = datetime.today()

    def get_calendar(self, listing_id: str):
        url = self.get_url(listing_id)
        response_data = self._api_request(url)
        self.__parse_response(response_data)

    def get_url(self, listing_id: str) -> str:
        _api_path = '/api/v3/PdpAvailabilityCalendar'
        query = {
            'operationName': 'PdpAvailabilityCalendar',
            'locale':        self._locale,
            'currency':      self._currency,
            'variables':     {
                "request": {
                    'count':     self.N_MONTHS,
                    'listingId': listing_id,
                    'month':     self.__today.month,
                    'year':      self.__today.year
                }
            },
            'extensions':    {
                'persistedQuery': {
                    'version':    1,
                    'sha256Hash': '8f08e03c7bd16fcad3c92a3592c19a8b559a0d0855a84028d1163d4733ed9ade'
                }
            }
        }
        self._put_json_param_strings(query)

        return self.build_airbnb_url(_api_path, query)

    def __parse_response(self, data: dict):
        calendar_months = data['merlin']['pdpAvailabilityCalendar']['calendarMonths']
        availability = {}
        for month in calendar_months:
            for day in month['days']:
                calendar_date = datetime.strptime(day['calendarDate'], '%Y-%m-%d')
                if calendar_date < self.__today:
                    continue  # skip dates in the past


class StartStaysCheckout(BaseEndpoint):
    def get_rates(self, product_id: str, start_date: str, end_date: str):
        _api_path = '/api/v3/startStaysCheckout'
        url = self.build_airbnb_url(_api_path, {
            'operationName': 'startStaysCheckout',
            'locale':        self._locale,
            'currency':      self._currency
        })
        payload = json.dumps({
            'operationName': 'startStaysCheckout',
            'variables':     {
                'input': {
                    'businessTravel':        {
                        'workTrip': False
                    },
                    'checkinDate':           start_date,
                    'checkoutDate':          end_date,
                    'guestCounts':           {
                        'numberOfAdults':   1,
                        'numberOfChildren': 0,
                        'numberOfInfants':  0,
                        'numberOfPets':     0
                    },
                    'guestCurrencyOverride': self._currency,
                    'lux':                   {},
                    'metadata':              {
                        'internalFlags': [
                            'LAUNCH_LOGIN_PHONE_AUTH'
                        ]
                    },
                    'org':                   {},
                    'productId':             product_id,
                    'china':                 {},
                    'quickPayData':          None
                }
            },
            'extensions':    {
                'persistedQuery': {
                    'version':    1,
                    'sha256Hash': '4a01261214aad9adf8c85202020722e6e05bfc7d5f3d0b865531f9a6987a3bd1'
                }
            }
        })
        return self._api_request(url, 'POST', payload)
