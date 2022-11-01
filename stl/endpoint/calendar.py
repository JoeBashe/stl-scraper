import json
import statistics

from datetime import date, datetime, timedelta
from itertools import groupby
from logging import Logger
from operator import itemgetter
from requests.exceptions import ConnectionError
from time import sleep

from stl.endpoint.base_endpoint import BaseEndpoint
from stl.endpoint.pdp import Pdp


class Pricing(BaseEndpoint):
    API_PATH = '/api/v3/startStaysCheckout'

    def get_pricing(self, checkin: str, checkout: str, listing_id: str) -> dict:
        """Get pricing object for a listing for specific dates."""
        # Get raw price data
        product_id = Pdp.get_product_id(listing_id)
        rates = self.get_rates(product_id, checkin, checkout)
        sections = rates['data']['startStayCheckoutFlow']['stayCheckout']['sections']
        if not (sections['temporaryQuickPayData'] and sections['temporaryQuickPayData']['bootstrapPaymentsJSON']):
            raise ValueError('Error retrieving pricing: {}'.format(sections['metadata']['errorData']['errorMessage']))

        quickpay_data = json.loads(sections['temporaryQuickPayData']['bootstrapPaymentsJSON'])
        return self.__normalize_pricing(
            quickpay_data['productPriceBreakdown']['priceBreakdown'],
            (datetime.strptime(checkout, '%Y-%m-%d') - datetime.strptime(checkin, '%Y-%m-%d')).days
        )

    def get_rates(self, product_id: str, start_date: str, end_date: str):
        url = BaseEndpoint.build_airbnb_url(self.API_PATH, {
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

    @staticmethod
    def __normalize_pricing(price_breakdown: dict, nights: int):
        """Normalize price line items. Throw ValueError if price data malformed."""
        price_items = price_breakdown['priceItems']
        if len(price_items) > 5:
            raise ValueError(
                'Unexpected extra section types:\n{}'.format(', '.join([pi['type'] for pi in price_items])))

        items = {}
        for type_name in ['ACCOMMODATION', 'AIRBNB_GUEST_FEE', 'CLEANING_FEE', 'DISCOUNT', 'TAXES']:
            type_items = [i for i in price_items if i['type'] == type_name]
            if not type_items:
                if type_name == 'ACCOMMODATION':
                    raise ValueError('No ACCOMMODATION pricing found: {}'.format(price_items))
                else:
                    continue  # Missing AIRBNB_GUEST_FEE, CLEANING_FEE, DISCOUNT or TAXES is ok

            if len(type_items) > 1:
                raise ValueError('Unexpected multiple section type: %s' % type_name)

            items[type_name] = type_items.pop()

        # Create normalized pricing object
        mega = 1_000_000  # one million
        price_accommodation = items['ACCOMMODATION']['total']['amountMicros'] / mega
        taxes = items['TAXES']['total']['amountMicros'] / mega if items.get('TAXES') else 0
        cleaning_fee = items['CLEANING_FEE']['total']['amountMicros'] / mega if items.get('CLEANING_FEE') else 0
        airbnb_fee = items['AIRBNB_GUEST_FEE']['total']['amountMicros'] / mega if items.get('AIRBNB_GUEST_FEE') else 0
        pricing = {
            'nights':              nights,
            'price_nightly':       price_accommodation / nights,
            'price_accommodation': price_accommodation,
            'price_cleaning':      cleaning_fee,
            'taxes':               taxes,
            'airbnb_fee':          airbnb_fee,
            'total':               price_breakdown['total']['total']['amountMicros'] / mega,
        }

        if items.get('DISCOUNT'):
            discount = -1 * (items['DISCOUNT']['total']['amountMicros'] / mega)
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


class Calendar(BaseEndpoint):
    API_PATH = '/api/v3/PdpAvailabilityCalendar'
    N_MONTHS = 12  # number of months of data to return; 12 months == 1 year

    def __init__(self, api_key: str, currency: str, logger: Logger, pricing: Pricing):
        super().__init__(api_key, currency, logger)
        self.__pricing = pricing
        self.__today = datetime.today()

    @staticmethod
    def get_date_ranges(status: str, booking_calendar: dict) -> list:
        """Given a booking calendar and a status of "available" or "booked", return a list of date range objects for
        either available or booked dates.
        """
        allowed_status = ['available', 'booked']
        if status not in allowed_status:
            raise ValueError('status must be one of "available" or "booked"')
        dates = [
            datetime.strptime(dt, '%Y-%m-%d').toordinal() for dt, is_booked in booking_calendar.items() if is_booked
        ] if status == 'booked' else [
            datetime.strptime(dt, '%Y-%m-%d').toordinal() for dt, is_booked in booking_calendar.items() if not is_booked
        ]
        ranges = []
        for k, g in groupby(enumerate(dates), lambda i: i[0] - i[1]):
            group = list(map(itemgetter(1), g))
            start_date = date.fromordinal(group[0])
            end_date = date.fromordinal(group[-1]) + timedelta(days=1)
            ranges.append({
                'start':  start_date,
                'end':    end_date,
                'length': (end_date - start_date).days
            })

        return ranges

    def get_calendar(self, listing_id: str) -> tuple:
        url = self.get_url(listing_id)
        response_data = self._api_request(url)
        return self.__get_booking_calendar(response_data)

    def get_rate_data(
            self,
            listing_id: str,
            ranges: list,
            min_nights: int = None,
            max_nights: int = None,
            full_data: bool = False
    ) -> dict:
        test_lengths = self.__get_test_lengths(max_nights, min_nights)
        pricing_data = {}
        for test_length in test_lengths:
            if test_length > max_nights:
                continue
            if test_length < min_nights:
                continue

            possible_ranges = [r for r in ranges if r.get('length') >= test_length]
            pd = None
            while possible_ranges and not pd:
                test_range = possible_ranges.pop()
                start_time = test_range['start'].strftime('%Y-%m-%d')
                end_time = (test_range['start'] + timedelta(days=test_length)).strftime('%Y-%m-%d')
                try:
                    pd = self.__pricing.get_pricing(start_time, end_time, listing_id)
                except (ValueError, RuntimeError) as e:
                    self._logger.error('{}: Could not get pricing data: {}'.format(listing_id, str(e)))
                    continue
                except ConnectionError as e:
                    self._logger.error('{}: Could not get pricing data: {}'.format(listing_id, str(e)))
                    # connection error due to network issues. wait for one minute for network connection to be
                    # re-established.
                    sleep(60)
                    continue

            if not pd:
                self._logger.warning('{}: Unable to find available {} day range'.format(listing_id, test_length))
                continue

            pricing_data[test_length] = pd

        if full_data or not pricing_data:
            return pricing_data

        # normalize data
        test_pricing = list(pricing_data.values()).pop()
        pricing_doc = {
            'price_nightly':  test_pricing['price_nightly'],
            'price_cleaning': test_pricing['price_cleaning'],
        }

        if pricing_data.get(7) and pricing_data[7].get('discount_weekly'):
            pricing_doc['discount_weekly'] = pricing_data[7]['discount_weekly']

        monthly_length = min_nights if min_nights > 28 else 28
        if pricing_data.get(monthly_length) and pricing_data[monthly_length].get('discount_monthly'):
            pricing_doc['discount_monthly'] = pricing_data[monthly_length]['discount_monthly']

        return pricing_doc

    def get_url(self, listing_id: str) -> str:
        """Get PdpAvailabilityCalendar URL."""
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

        return BaseEndpoint.build_airbnb_url(self.API_PATH, query)

    @staticmethod
    def __get_test_lengths(max_nights: int, min_nights: int) -> list:
        """Generate a list of lengths of stays to be used to determine pricing, based upon listing requirements of
        max_nights and min_nights."""
        if min_nights > 28:  # monthly only
            return [min_nights]
        elif min_nights >= 7:
            if max_nights >= 28:  # weekly and monthly
                return [min_nights, 28]
            else:  # weekly only
                return [min_nights]
        else:  # min nights < 7
            if max_nights >= 28:  # daily, weekly, and monthly
                return [min_nights, 7, 28]
            elif max_nights >= 7:  # daily and weekly
                return [min_nights, 7]
            else:  # daily only
                return [min_nights]

    def __get_booking_calendar(self, data: dict) -> tuple:
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
                if day['available']:
                    if first_available_date is None:
                        first_available_date = day['calendarDate']
                    booking_calendar[day['calendarDate']] = False
                else:
                    booking_calendar[day['calendarDate']] = True
                    booked_days += 1

        min_nights = statistics.mode([day['minNights'] for month in calendar_months for day in month['days']])
        max_nights = statistics.mode([day['maxNights'] for month in calendar_months for day in month['days']])

        return booking_calendar, min_nights, max_nights
