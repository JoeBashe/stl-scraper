import json

from datetime import date, datetime, timedelta
from itertools import groupby
from logging import Logger
from operator import itemgetter

from stl.endpoint.base_endpoint import BaseEndpoint
from stl.endpoint.pdp import Pdp


class Pricing(BaseEndpoint):

    def get_pricing(self, checkin: str, checkout: str, listing_id: str):
        """Get total price for a listing for specific dates."""
        # Get raw price data
        product_id = Pdp.get_product_id(listing_id)
        rates = self.get_rates(product_id, checkin, checkout)
        sections = rates['data']['startStayCheckoutFlow']['stayCheckout']['sections']
        quickpay_data = json.loads(sections['temporaryQuickPayData']['bootstrapPaymentsJSON'])
        price_breakdown = quickpay_data['productPriceBreakdown']['priceBreakdown']
        price_items = price_breakdown['priceItems']
        nights = (datetime.strptime(checkout, '%Y-%m-%d') - datetime.strptime(checkin, '%Y-%m-%d')).days

        if len(price_items) > 5:
            raise ValueError(
                'Unexpected extra section types:\n{}'.format(', '.join([pi['type'] for pi in price_items])))

        # Parse price line items
        items = {}
        for type_name in ['ACCOMMODATION', 'AIRBNB_GUEST_FEE', 'CLEANING_FEE', 'DISCOUNT', 'TAXES']:
            type_items = [i for i in price_items if i['type'] == type_name]
            if not type_items:
                if type_name != 'DISCOUNT':
                    raise ValueError('Unexpected missing section type: %s' % type_name)
                continue  # Missing discount is ok
            if len(type_items) > 1:
                raise ValueError('Unexpected multiple section type: %s' % type_name)
            items[type_name] = type_items.pop()

        # Create normalized pricing object
        price_accommodation = items['ACCOMMODATION']['total']['amountMicros'] / 1000000
        taxes = items['TAXES']['total']['amountMicros'] / 1000000
        pricing = {
            'nights':              nights,
            'price_nightly':       price_accommodation / nights,
            'price_accommodation': price_accommodation,
            'price_cleaning':      items['CLEANING_FEE']['total']['amountMicros'] / 1000000,
            'taxes':               taxes,
            'airbnb_fee':          items['AIRBNB_GUEST_FEE']['total']['amountMicros'] / 1000000,
            'total':               price_breakdown['total']['total']['amountMicros'] / 1000000,
        }

        if items.get('DISCOUNT'):
            discount = -1 * (items['DISCOUNT']['total']['amountMicros'] / 1000000)
            pricing['discount'] = discount
            pricing['tax_rate'] = taxes / (price_accommodation + pricing['price_cleaning'] - discount)
            if 'Weekly discount' == items['DISCOUNT']['localizedTitle']:
                pricing['discount_monthly'] = None
                pricing['discount_weekly'] = discount / price_accommodation
            elif 'Monthly discount' == items['DISCOUNT']['localizedTitle']:
                pricing['discount_monthly'] = discount / price_accommodation
                pricing['discount_weekly'] = None
            else:
                raise ValueError('Unhandled discount type: %s' % items['DISCOUNT']['localizedTitle'])
        else:
            pricing['tax_rate'] = taxes / (price_accommodation + pricing['price_cleaning'])

        return pricing

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

    def __init__(self, api_key: str, currency: str, pricing: Pricing, logger: Logger):
        super().__init__(api_key, currency)
        self.__logger = logger
        self.__pricing = pricing
        self.__today = datetime.today()

    def get_calendar(self, listing_id: str) -> dict:
        url = self.get_url(listing_id)
        response_data = self._api_request(url)
        return self.__get_booking_calendar(response_data)

    def get_rate_data(self, listing_id: str, booking_calendar: dict) -> dict:
        ranges = self.__get_available_date_ranges(booking_calendar)
        # run test queries to get monthly, weekly, and daily rates
        pricing_data = {}
        for test_length in [28, 7, 1]:  # check monthly, weekly and daily pricing
            possible_ranges = [r for r in ranges if r.get('length') >= test_length]
            if not possible_ranges:
                self.__logger.warning('{}: Unable to find available {} day range'.format(listing_id, test_length))
                continue
            test_range = possible_ranges.pop()
            start_time = test_range['start'].strftime('%Y-%m-%d')
            end_time = (test_range['start'] + timedelta(days=test_length)).strftime('%Y-%m-%d')
            pricing_data[test_length] = self.__pricing.get_pricing(
                start_time,
                end_time,
                listing_id
            )

        return pricing_data

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

    @staticmethod
    def __get_available_date_ranges(booking_calendar: dict) -> list:
        # get list of date ranges that are free for test price queries
        available_dates = [datetime.strptime(dt, '%Y-%m-%d').toordinal()
                           for dt, is_booked in booking_calendar.items() if not is_booked]
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

        return ranges

    def __get_booking_calendar(self, data: dict) -> dict:
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

        return booking_calendar
