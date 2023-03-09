import base64
import lxml.html
import pycountry
import re

from datetime import datetime
from logging import Logger

from stl.endpoint.base_endpoint import BaseEndpoint
from stl.geo.geocode import Geocoder


class Pdp(BaseEndpoint):
    API_PATH = '/api/v3/PdpPlatformSections'

    AMENITIES = {
        1:    'tv',
        4:    'wifi',
        5:    'a/c',
        8:    'kitchen',
        10:   'parking',
        21:   'elevator',
        30:   'heating',
        33:   'washer',
        34:   'dryer',
        35:   'smoke alarm',
        36:   'carbon monoxide alarm',
        37:   'first aid kit',
        39:   'fire extinguisher',
        40:   'essentials',
        41:   'shampoo',
        44:   'hangers',
        45:   'hair dryer',
        46:   'iron',
        47:   'dedicated workspace',
        51:   'self check-in',
        54:   'lockbox',
        57:   'private entrance',
        77:   'hot water',
        85:   'bed linens',
        86:   'extra pillows and blankets',
        89:   'microwave',
        90:   'coffee maker',
        91:   'refrigerator',
        92:   'dishwasher',
        93:   'dishes and silverware',
        94:   'cooking basics',
        95:   'oven',
        96:   'stove',
        99:   'bbq grill',
        100:  'private patio or balcony',
        101:  'private backyard',
        104:  'long term stays allowed',
        137:  'hot water kettle',
        139:  'ceiling fan',
        236:  'dining table',
        280:  'outdoor furniture',
        308:  'freezer',
        322:  'blender',
        611:  'shower gel',
        625:  'baking sheet',
        626:  'barbecue utensils',
        657:  'conditioner',
        665:  'cleaning products',
        667:  'drying rack',
        671:  'clothing storage',
        672:  'wine glasses',
        9999: 'security cameras'
    }

    SECTION_NAMES = ['amenities', 'description', 'host_profile', 'location', 'policies']

    def __init__(self, api_key: str, currency: str,  proxy: str, ignore_cert: bool, throttle: bool, logger: Logger):
        super().__init__(api_key, currency, proxy, ignore_cert,throttle, logger)
        self.__geocoder = Geocoder()
        self.__regex_amenity_id = re.compile(r'^([a-z0-9]+_)+([0-9]+)_')

    @staticmethod
    def get_product_id(listing_id: str) -> str:
        return base64.b64encode(bytes(f'StayListing:{listing_id}', 'utf-8')).decode('utf-8')

    def get_listing(self, listing_id: str, data_cache: dict, geography: dict, reviews: dict) -> dict:
        product_id = self.get_product_id(listing_id)
        response = self.get_raw_listing(listing_id)
        return self.__parse_listing_contents(response, data_cache[listing_id], geography, reviews) | {
            'product_id': product_id,
            'source':     self.SOURCE,
            'updated_at': datetime.utcnow(),
        }

    def get_raw_listing(self, listing_id: str) -> dict:
        url = self.__get_url(listing_id)
        return self._api_request(url)

    def collect_listings_from_sections(self, data: dict, geography: dict, data_cache: dict):
        """Get listings from "sections" (i.e. search results page sections)."""
        sections = data['data']['dora']['exploreV3']['sections']
        listing_ids = []
        for section in [s for s in sections if s['sectionComponentType'] == 'listings_ListingsGrid_Explore']:
            for listing_item in section.get('items'):
                listing_id = listing_item['listing']['id']
                self.__collect_listing_data(listing_item, geography, data_cache)
                listing_ids.append(listing_id)

        return listing_ids

    def __collect_listing_data(self, listing_item: dict, geography: dict, data_cache: dict):
        """Collect listing data from search results, save in _data_cache. 

        The section data for each search result listing will later be combined with the PDP listing data in the 
        `parse_listing_contents()` method.
        """
        listing = listing_item['listing']
        pricing = listing_item['pricingQuote'] or {}
        city, neighborhood = self.__determine_city_and_neighborhood(listing, geography)

        data_cache[listing['id']] = {
            # get general data
            'avg_rating':             listing['avgRating'],
            'bathrooms':              listing['bathrooms'],
            'bedrooms':               listing['bedrooms'],
            'beds':                   listing['beds'],
            'business_travel_ready':  listing['isBusinessTravelReady'],
            'city':                   city,
            'host_id':                listing['user']['id'],
            'latitude':               listing['lat'],
            'longitude':              listing['lng'],
            'name':                   listing['name'],
            'neighborhood':           neighborhood,
            'neighborhood_overview':  listing['neighborhoodOverview'],
            'person_capacity':        listing['personCapacity'],
            'photo_count':            listing['pictureCount'],
            'photos':                 [p['picture'] for p in listing['contextualPictures']],
            'review_count':           listing['reviewsCount'],
            'room_and_property_type': listing['roomAndPropertyType'],
            'room_type':              listing['roomType'],
            'room_type_category':     listing['roomTypeCategory'],
            'star_rating':            listing['starRating'],
        }
        if pricing:
            # add pricing data
            data_cache[listing['id']] |= {
                'monthly_price_factor': pricing.get('monthlyPriceFactor'),
                'weekly_price_factor':  pricing.get('weeklyPriceFactor'),
                'price_rate':           self.__get_price_rate(pricing),
                'price_rate_type':      self.__get_rate_type(pricing),
                'total_price':          self.__get_total_price(pricing)
            }

    def __get_url(self, listing_id: str):
        query = {
            'operationName': 'PdpPlatformSections',
            'locale':        self._locale,
            'currency':      self._currency
        }
        data = {
            'variables':  {
                'request': {
                    'id':                            listing_id,
                    'layouts':                       ['SIDEBAR', 'SINGLE_COLUMN'],
                    'pdpTypeOverride':               None,
                    'translateUgc':                  None,
                    'preview':                       False,
                    'bypassTargetings':              False,
                    'displayExtensions':             None,
                    'adults':                        '1',
                    'children':                      None,
                    'infants':                       None,
                    'causeId':                       None,
                    'disasterId':                    None,
                    'priceDropSource':               None,
                    'promotionUuid':                 None,
                    'selectedCancellationPolicyId':  None,
                    'forceBoostPriorityMessageType': None,
                    'privateBooking':                False,
                    'invitationClaimed':             False,
                    'discountedGuestFeeVersion':     None,
                    'staysBookingMigrationEnabled':  False,
                    'useNewSectionWrapperApi':       False,
                    'previousStateCheckIn':          None,
                    'previousStateCheckOut':         None,
                    'federatedSearchId':             None,
                    'interactionType':               None,
                    'searchId':                      None,
                    'sectionIds':                    None,
                    'checkIn':                       None,
                    'checkOut':                      None,
                    'p3ImpressionId':                'p3_1608841700_z2VzPeybmBEdZG20'
                }
            },
            'extensions': {
                'persistedQuery': {
                    'version':    1,
                    'sha256Hash': '625a4ba56ba72f8e8585d60078eb95ea0030428cac8772fde09de073da1bcdd0'
                }
            }
        }

        self._put_json_param_strings(data)

        url = BaseEndpoint.build_airbnb_url(self.API_PATH, query)
        url += '&variables=%s' % data['variables']
        url += '&extensions=%s' % data['extensions']

        return url

    def __parse_listing_contents(self, data: dict, listing_data_cached: dict, geography: dict, reviews: dict) -> dict:
        """Obtain data from an individual listing page, combine with cached data, and return dict."""
        # Collect base data
        pdp_sections = data['data']['merlin']['pdpSections']
        listing_id = pdp_sections['id']
        sections = pdp_sections['sections']
        metadata = pdp_sections['metadata']
        logging_data = metadata['loggingContext']['eventDataLogging']

        # Get section data
        section_data = {}
        for section_name in self.SECTION_NAMES:
            detail_list = [s for s in sections if s['sectionId'] == '{}_DEFAULT'.format(section_name.upper())]
            if not detail_list:
                continue
            section_data[section_name] = detail_list[0]['section']

        # Collect amenity group data
        if section_data.get('amenities'):
            amenities_groups = section_data['amenities']['seeAllAmenitiesGroups']
            amenities_access = [g['amenities'] for g in amenities_groups if g['title'] == 'Guest access']
            amenities_avail = [amenity for g in amenities_groups for amenity in g['amenities'] if amenity['available']]
        else:
            amenities_access = amenities_avail = []

        # Collect house rules
        house_rules = []
        listing_expectations = None
        if section_data.get('policies'):
            if section_data['policies'].get('listingExpectations'):
                listing_expectations = self.__render_titles(section_data['policies']['listingExpectations'])
            if section_data['policies'].get('houseRules'):
                house_rules = [r['title'] for r in section_data['policies']['houseRules']]

        # Convert description to plaintext if it exists
        description = ''
        if section_data.get('description') and section_data['description'].get('htmlDescription'):
            description = self.__html_to_text(section_data['description']['htmlDescription']['htmlText'])

        # Structure data
        item = {
            'id':                     listing_id,
            'access':                 self.__render_titles(amenities_access[0]) if amenities_access else None,
            'additional_house_rules': section_data['policies'].get('additionalHouseRules'),
            'allows_events':          'No parties or events' in house_rules,
            'amenities':              self.__render_titles(amenities_avail, sep=' - ', join=False),
            'amenity_ids':            list(self.__get_amenity_ids(amenities_avail)),
            'avg_rating':             listing_data_cached['avg_rating'],
            'bathrooms':              listing_data_cached['bathrooms'],
            'bedrooms':               listing_data_cached['bedrooms'],
            'beds':                   listing_data_cached['beds'],
            'business_travel_ready':  listing_data_cached['business_travel_ready'],
            'can_instant_book':       metadata['bookingPrefetchData']['canInstantBook'],
            'city':                   listing_data_cached.get('city', geography['city']),
            'coordinates':            {'lon': listing_data_cached['longitude'], 'lat': listing_data_cached['latitude']},
            'country':                geography['country'],
            'description':            description,
            'host_id':                listing_data_cached['host_id'],
            'house_rules':            house_rules,
            'is_hotel':               metadata['bookingPrefetchData']['isHotelRatePlanEnabled'],
            'latitude':               listing_data_cached['latitude'],
            'listing_expectations':   listing_expectations,
            'longitude':              listing_data_cached['longitude'],
            'monthly_price_factor':   listing_data_cached.get('monthly_price_factor'),
            'name':                   listing_data_cached.get('name', listing_id),
            'neighborhood':           listing_data_cached.get('neighborhood'),
            'neighborhood_overview':  listing_data_cached.get('neighborhood_overview'),
            'person_capacity':        listing_data_cached['person_capacity'],
            'photo_count':            listing_data_cached['photo_count'],
            'photos':                 listing_data_cached['photos'],
            'place_id':               geography['placeId'],
            'price_rate':             listing_data_cached.get('price_rate'),
            'price_rate_type':        listing_data_cached.get('price_rate_type'),
            'province':               geography.get('province'),
            'rating_accuracy':        logging_data['accuracyRating'],
            'rating_checkin':         logging_data['checkinRating'],
            'rating_cleanliness':     logging_data['cleanlinessRating'],
            'rating_communication':   logging_data['communicationRating'],
            'rating_location':        logging_data['locationRating'],
            'rating_value':           logging_data['valueRating'],
            'review_count':           listing_data_cached['review_count'],
            'reviews':                reviews,
            'room_and_property_type': listing_data_cached['room_and_property_type'],
            'room_type':              listing_data_cached['room_type'],
            'room_type_category':     listing_data_cached['room_type_category'],
            'satisfaction_guest':     logging_data['guestSatisfactionOverall'],
            'star_rating':            listing_data_cached['star_rating'],
            'state':                  geography['state'],
            'total_price':            listing_data_cached.get('total_price'),
            'url':                    "https://www.airbnb.com/rooms/{}".format(listing_id),
            'weekly_price_factor':    listing_data_cached.get('weekly_price_factor')
        }

        self.__get_detail_property(
            item, 'transit', 'Getting around', section_data['location'].get('seeAllLocationDetails'), 'content')

        if section_data.get('host_profile'):
            self.__get_detail_property(
                item, 'interaction', 'During your stay', section_data['host_profile'].get('hostInfos'), 'html')

        return item

    def __determine_city_and_neighborhood(self, listing: dict, geography: dict):
        """Determine city and neighborhood. 

        It is way more complicated to get the city name than you'd expect. Airbnb sometimes puts the 
        neighborhood/borough/district into the city field, or give results from different cities entirely. Therefore,
        we use reverse geocoding (and, of course, advanced AI) to determine what the actual city name is. As a bonus,
        we also try to get the neighborhood.
        """
        public_address_components = list(map(str.strip, filter(bool, listing['publicAddress'].split(','))))
        search_city = geography['city']

        city = Pdp.__capitalize_first(listing['city'])
        neighborhood = listing['neighborhood']

        localized_city = Pdp.__capitalize_first(listing['localizedCity'])
        localized_neighborhood = listing['localizedNeighborhood']

        if search_city == city:
            return city, localized_neighborhood or neighborhood
        elif search_city == localized_city:
            city = localized_city

        address_city, address_neighborhood, address_district = None, None, None
        unknown_components = []
        for component in filter(bool, public_address_components):
            if component == search_city:
                address_city = component
            elif component == localized_neighborhood:
                address_neighborhood = component
            else:
                try:
                    result = pycountry.countries.lookup(component) or pycountry.subdivisions.lookup(component)
                    continue  # skip countries and state/province subdivisions
                except LookupError:
                    unknown_components.append(component)

        if address_city and localized_neighborhood:
            return address_city, localized_neighborhood

        n_unknown_componenets = len(unknown_components)
        if n_unknown_componenets == 0:
            return address_city, neighborhood
        elif n_unknown_componenets == 1:
            if address_neighborhood and address_city:
                address_district = unknown_components.pop()
            elif address_city:
                address_neighborhood = unknown_components.pop()

        reverse_geo_address = self.__geocoder.reverse(listing['lat'], listing['lng'])
        if reverse_geo_address and 'city' in reverse_geo_address:
            if reverse_geo_address['city'] in [search_city, city, localized_city] or self.__geocoder.is_city(reverse_geo_address['city'], reverse_geo_address['country']):
                return reverse_geo_address['city'], localized_neighborhood

        if self.__geocoder.is_city((city or localized_city), reverse_geo_address['country']):
            return city or localized_city, neighborhood

        return city, neighborhood

    def __get_amenity_ids(self, amenities: list):
        """Extract amenity id from `id` string field."""
        for amenity in amenities:
            match = self.__regex_amenity_id.match(amenity['id'])
            yield int(match.group(match.lastindex))

    def __get_detail_property(self, item: dict, prop: str, title: str, prop_list: list, key: str):
        """Search for matching title in property list for prop. If exists, add htmlText for key to item."""
        if title in [i['title'] for i in prop_list]:
            item[prop] = self.__html_to_text([i[key]['htmlText'] for i in prop_list if i['title'] == title][0])
        else:
            item[prop] = None

    @staticmethod
    def __capitalize_first(name: str | None) -> str:
        if name:
            return name[0].upper() + name[1:]
        return name

    @staticmethod
    def __get_price_key(pricing) -> str:
        return 'price' if 'price' in pricing['structuredStayDisplayPrice']['primaryLine'] else 'discountedPrice'

    @staticmethod
    def __get_price_rate(pricing) -> int | None:
        if pricing:
            price_key = Pdp.__get_price_key(pricing)
            res=pricing['structuredStayDisplayPrice']['primaryLine'][price_key].replace('\xa0',' ')
            return int ( ''.join(filter(str.isdigit, res) ) )
        return None

    @staticmethod
    def __get_rate_type(pricing) -> str | None:
        if pricing:
            return pricing['structuredStayDisplayPrice']['primaryLine']['qualifier']

        return None

    @staticmethod
    def __get_total_price(pricing) -> int | None:
        if pricing['structuredStayDisplayPrice']['secondaryLine']:
            price = pricing['structuredStayDisplayPrice']['secondaryLine']['price']
        else:
            price_key = Pdp.__get_price_key(pricing)
            price = pricing['structuredStayDisplayPrice']['primaryLine'][price_key]

        amount_match = int ( ''.join(filter(str.isdigit, price) ) )

        if not amount_match:
            raise ValueError('No amount match found for price: %s' % price)

        return int(amount_match)

    @staticmethod
    def __html_to_text(html: str) -> str:
        """Get plaintext from HTML."""
        return lxml.html.document_fromstring(html).text_content()

    @staticmethod
    def __render_titles(title_list: list, sep: str = ': ', join: bool = True) -> str | list:
        """Render list of objects with titles and subtitles into string."""
        lines = []
        for t in title_list:
            line = '{}{}{}'.format(t['title'], sep, t['subtitle']) if t.get('subtitle') else t.get('title')
            lines.append(line)

        return '\n'.join(lines) if join else lines
