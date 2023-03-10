from datetime import datetime
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk, scan
from elasticsearch.exceptions import RequestError

from stl.persistence import PersistenceInterface


class Elastic(PersistenceInterface):
    INDEX_MAPPINGS = {
        "properties": {
            "access":                 {"type": "text"},
            "additional_house_rules": {"type": "text"},
            "allows_events":          {"type": "boolean"},
            "amenities":              {"type": "keyword"},
            "amenity_ids":            {"type": "keyword"},
            "avg_rating":             {"type": "float"},
            "baths_half":             {"type": "short"},
            "baths_total":            {"type": "short"},
            "bathrooms":              {"type": "float"},
            "bedrooms":               {"type": "short"},
            "beds":                   {"type": "integer"},
            "bookings":               {
                "type":       "nested",
                "properties": {"date": {"type": "date", "format": "yyyy-MM-dd"}}
            },
            "business_travel_ready":  {"type": "boolean"},
            "city":                   {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
            "country":                {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
            "coordinates":            {"type": "geo_point"},
            "description":            {"type": "text"},
            "discount_monthly":       {"type": "float"},
            "discount_weekly":        {"type": "float"},
            "host_id":                {"type": "integer", "fields": {"keyword": {"type": "keyword"}}},
            "house_rules":            {"type": "text"},
            "interaction":            {"type": "text"},
            "is_hotel":               {"type": "boolean"},
            "latitude":               {"type": "double"},
            "listing_key":            {"type": "keyword"},
            "listing_key_numeric":    {"type": "long"},
            "longitude":              {"type": "double"},
            "name":                   {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
            "neighborhood_overview":  {"type": "text"},
            "person_capacity":        {"type": "integer"},
            "photo_count":            {"type": "integer"},
            "photos":                 {"type": "keyword"},
            "place_id":               {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
            "price_nightly":          {"type": "float"},
            "price_cleaning":         {"type": "float"},
            "province":               {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
            "rating_accuracy":        {"type": "float"},
            "rating_checkin":         {"type": "float"},
            "rating_cleanliness":     {"type": "float"},
            "rating_communication":   {"type": "float"},
            "rating_location":        {"type": "float"},
            "rating_value":           {"type": "float"},
            "review_count":           {"type": "integer"},
            "reviews":                {"type": "nested"},
            "room_and_property_type": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
            "room_type":              {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
            "room_type_category":     {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
            "satisfaction_guest":     {"type": "float"},
            "site_id":                {"type": "integer"},
            "source":                 {"type": "keyword"},
            "star_rating":            {"type": "float"},
            "state":                  {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
            "street_number":          {"type": "keyword"},
            "street_number_numeric":  {"type": "integer"},
            "transit":                {"type": "text"},
            "url":                    {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
            "year_built":             {"type": "integer"}
        }
    }

    def __init__(self, es: Elasticsearch, index: str):
        self.__es = es
        self.__index = index

    def create_index_if_not_exists(self, index_name: str):
        """Create an index if it doesn't already exist."""
        if self.__es.indices.exists(index=index_name):
            return
        try:
            self.__es.indices.create(index=index_name, ignore=1, mappings=self.INDEX_MAPPINGS)
        except RequestError as re:
            if re.error != 'resource_already_exists_exception':
                raise

    def delete(self, listing_id: str):
        """Delete a listing by id."""
        self.__es.delete(index=self.__index, id=listing_id)

    def get_all_index_ids(self, since: str):
        """Get all index ids not updated since "since" (default: "1d"), except those marked as deleted."""
        query = {
            "query": {
                "bool": {
                    "must_not": [
                        {
                            "term": {
                                "deleted": {
                                    "value": True
                                }
                            }
                        }
                    ],
                    "must":     [
                        {
                            "range": {
                                "updated_at": {
                                    "lte": "now-{}".format(since)
                                }
                            }
                        }
                    ]
                }
            }
        }
        hits = scan(
            self.__es,
            query=query,
            scroll='2m',
            index=self.__index
        )
        return (hit['_id'] for hit in hits)

    def mark_deleted(self, listing_id: str):
        """Mark a listing as deleted by setting the 'deleted' field to True."""
        self.__es.update(index=self.__index, id=listing_id, doc={'deleted': True})

    def save(self, query: str, listings: list,continuous:bool=False):
        """Bulk save listings by upsert."""
        bulk(self.__es, index=self.__index, actions=[{
            '_op_type':      'update',
            '_id':           listing['id'],
            'doc':           listing,
            'doc_as_upsert': True
        } for listing in listings])

    def update_calendar(self, listing_id: str, calendar: dict):
        booked_dates = [dt for dt, is_booked in calendar.items() if is_booked]
        exists_booking_field = self.__es.search(index=self.__index, query={
            "bool": {
                "must":   {
                    "exists": {
                        "field": "bookings"
                    }
                },
                "filter": {
                    "term": {"_id": listing_id}
                }
            }
        })
        bookings = [{'date': dt} for dt in booked_dates]
        if exists_booking_field.body['hits']['hits']:
            script = {
                "source": """
                    def updated = false;
                    for (booking in params.bookings) {
                        if (!ctx._source.bookings.contains(booking)) {
                            ctx._source.bookings.add(booking);
                            updated = true;
                        }
                    }
                    if (updated) {
                        // sort bookings
                        ctx._source.bookings.sort((a,b) -> a.date == b.date 
                            ? 0 
                            : ZonedDateTime.parse(a.date + "T00:00:00Z").isBefore(ZonedDateTime.parse(b.date + "T00:00:00Z"))
                                ? -1 
                                : 1
                        );
                    }
                    // mark updated because we "touched" this listing
                    ctx._source.updated_at = params.now;
                """,
                "params": {
                    "bookings": bookings,
                    "now":      datetime.utcnow()
                }
            }
            self.__es.update(index=self.__index, id=listing_id, script=script)
        else:
            self.__es.update(index=self.__index, id=listing_id, doc={
                'bookings':   bookings,
                'updated_at': datetime.utcnow()
            })

    def update_pricing(self, listing_id: str, pricing: dict, min_nights: int = None, max_nights: int = None):
        if max_nights:
            pricing['nights_max'] = max_nights
        if min_nights:
            pricing['nights_min'] = min_nights

        self.__es.update(index=self.__index, id=listing_id, doc=pricing)
