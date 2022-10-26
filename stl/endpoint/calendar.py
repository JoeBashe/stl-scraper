import json

from datetime import date, datetime, timedelta
from itertools import groupby
from operator import itemgetter

from stl.endpoint.base_endpoint import BaseEndpoint
from stl.endpoint.pdp import Pdp


class Pricing(BaseEndpoint):

    def get_pricing(self, checkin: str, checkout: str, listing_id: str):
        """Get total price for a listing for specific dates."""
        product_id = Pdp.get_product_id(listing_id)
        rates = self.get_rates(product_id, checkin, checkout)
        sections = rates['data']['startStayCheckoutFlow']['stayCheckout']['sections']
        quickpay_data = json.loads(sections['temporaryQuickPayData']['bootstrapPaymentsJSON'])
        price_breakdown = quickpay_data['productPriceBreakdown']['priceBreakdown']

        item_accommodation = [i for i in price_breakdown['priceItems'] if i['type'] == 'ACCOMMODATION'].pop()
        item_cleaning_fee = [i for i in price_breakdown['priceItems'] if i['type'] == 'CLEANING_FEE'].pop()
        item_discount = [i for i in price_breakdown['priceItems'] if i['type'] == 'DISCOUNT'].pop()
        item_taxes = [i for i in price_breakdown['priceItems'] if i['type'] == 'TAXES'].pop()
        nights = (datetime.strptime(checkout, '%Y-%m-%d') - datetime.strptime(checkin, '%Y-%m-%d')).days

        return {
            'nights':              nights,
            'price_nightly':       item_accommodation['total']['amountMicros'] / (1000000 * nights),
            'price_accommodation': item_accommodation['total']['amountMicros'] / 1000000,
            'discount':            item_cleaning_fee['total']['amountMicros'] / 1000000,
            'price_cleaning':      item_discount['total']['amountMicros'] / 1000000,
            'taxes':               item_taxes['total']['amountMicros'] / 1000000,
            'total':               price_breakdown['total']['total']['amountMicros'] / 1000000,
        }

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


class Calendar(BaseEndpoint):
    N_MONTHS = 12  # number of months of data to return; 12 months == 1 year

    def __init__(self, api_key: str, currency: str, pricing: Pricing):
        super().__init__(api_key, currency)
        self.__pricing = pricing
        self.__today = datetime.today()

    def get_calendar(self, listing_id: str):
        url = self.get_url(listing_id)
        response_data = self._api_request(url)
        self.__parse_response(listing_id, response_data)

    def get_url(self, listing_id: str) -> str:
        """Get PdpAvailabilityCalendar URL."""
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

    def __parse_response(self, listing_id: str, data: dict) -> dict:
        calendar_months = data['data']['merlin']['pdpAvailabilityCalendar']['calendarMonths']
        first_available_date = None
        booking_calendar = {}
        for month in calendar_months:
            booked_days = total_days = 0
            for day in month['days']:
                total_days += 1
                calendar_date = datetime.strptime(day['calendarDate'], '%Y-%m-%d')
                if calendar_date < self.__today:
                    continue  # skip dates in the past

                # is either today or in the future
                if day['availableForCheckin']:
                    if first_available_date is None:
                        first_available_date = day['calendarDate']
                    booking_calendar[day['calendarDate']] = False
                else:
                    booking_calendar[day['calendarDate']] = True
                    booked_days += 1

            print('{}-{} occupancy ratio: {:.2f}'.format(month['year'], month['month'], booked_days / total_days))

        # get list of date ranges that are free for test price queries
        available_dates = [
            datetime.strptime(dt, '%Y-%m-%d').toordinal()
            for dt, is_booked in booking_calendar.items() if not is_booked
        ]
        ranges = []
        for k, g in groupby(enumerate(available_dates), lambda i: i[0] - i[1]):
            group = list(map(itemgetter(1), g))
            start_date = date.fromordinal(group[0])
            end_date = date.fromordinal(group[-1]) + timedelta(days=1)
            ranges.append({
                'start':  start_date,
                'end':    end_date,
                'length': (end_date - start_date).days
            })

        for test_length in [28, 7, 1]:  # check monthly, weekly and daily pricing
            test_range = [r for r in ranges if r.get('length') >= test_length].pop()
            start_time = test_range['start'].strftime('%Y-%m-%d')
            end_time = (test_range['start'] + timedelta(days=test_length)).strftime('%Y-%m-%d')
            pricing = self.__pricing.get_pricing(
                start_time,
                end_time,
                listing_id
            )
            pass

        return booking_calendar
