from elasticsearch import Elasticsearch

from Stl.Persistence.PersistenceInterface import PersistenceInterface


class Elastic(PersistenceInterface):

    def __init__(self, es: Elasticsearch, index: str):
        self.__es = es
        self.__index = index

    def save(self, query: str, listings: list):
        self.__es.bulk(operations=[{
            '_op_type':      'update',
            '_id':           listing['id'],
            '_index':        self.__index,
            'doc':           listing,
            'doc_as_upsert': True
        } for listing in listings])
