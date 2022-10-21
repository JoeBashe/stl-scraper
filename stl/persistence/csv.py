import csv
import os.path

from stl.persistence.PersistenceInterface import PersistenceInterface


class Csv(PersistenceInterface):

    def __init__(self, project_path: str):
        self.__project_path = project_path

    def save(self, query: str, listings: list):
        csv_path = os.path.join(self.__project_path, '{}.csv'.format(query))
        with open(csv_path, 'w') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=listings[0].keys())
            writer.writeheader()
            writer.writerows(listings)
