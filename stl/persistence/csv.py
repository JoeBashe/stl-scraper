import csv

from stl.persistence import PersistenceInterface


class Csv(PersistenceInterface):

    def __init__(self, csv_path: str):
        self.__csv_path = csv_path

    def save(self, query: str, listings: list):
        with open(self.__csv_path, 'w', encoding='utf-8', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=listings[0].keys())
            writer.writeheader()
            writer.writerows(listings)
