from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk, scan
from elasticsearch.exceptions import RequestError

from stl.persistence.persistence_interface import PersistenceInterface


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
            "business_travel_ready":  {"type": "boolean"},
            "city":                   {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
            "country":                {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
            "coordinates":            {"type": "geo_point"},
            "description":            {"type": "text"},
            "host_id":                {"type": "integer", "fields": {"keyword": {"type": "keyword"}}},
            "house_rules":            {"type": "text"},
            "interaction":            {"type": "text"},
            "is_hotel":               {"type": "boolean"},
            "latitude":               {"type": "double"},
            "listing_key":            {"type": "keyword"},
            "listing_key_numeric":    {"type": "long"},
            "longitude":              {"type": "double"},
            "monthly_price_factor":   {"type": "float"},
            "name":                   {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
            "neighborhood_overview":  {"type": "text"},
            "person_capacity":        {"type": "integer"},
            "photo_count":            {"type": "integer"},
            "photos":                 {"type": "keyword"},
            "place_id":               {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
            "price_rate":             {"type": "float"},
            "price_rate_type":        {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
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
            "star_rating":            {"type": "float"},
            "state":                  {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
            "street_number":          {"type": "keyword"},
            "street_number_numeric":  {"type": "integer"},
            "transit":                {"type": "text"},
            "url":                    {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
            "weekly_price_factor":    {"type": "float"},
            "year_built":             {"type": "integer"}
        }
    }

    def __init__(self, es: Elasticsearch, index: str):
        self.__es = es
        self.__index = index

    def create_index_if_not_exists(self, index_name: str):
        if self.__es.indices.exists(index=index_name):
            return
        try:
            self.__es.indices.create(index=index_name, ignore=1, mappings=self.INDEX_MAPPINGS)
        except RequestError as re:
            if re.error != 'resource_already_exists_exception':
                raise

    def delete(self, listing_id: str):
        self.__es.delete(index=self.__index, id=listing_id)

    def get_all_index_ids(self):
        hits = scan(
            self.__es,
            query={"query": {"match_all": {}}},
            scroll='1m',
            index=self.__index
        )
        return (hit['_id'] for hit in hits)

    def save(self, query: str, listings: list):
        bulk(self.__es, index=self.__index, actions=[{
            '_op_type':      'update',
            '_id':           listing['id'],
            'doc':           listing,
            'doc_as_upsert': True
        } for listing in listings])
