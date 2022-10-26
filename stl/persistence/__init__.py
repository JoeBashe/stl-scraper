from abc import ABC, abstractmethod


class PersistenceInterface(ABC):
    @abstractmethod
    def save(self, query: str, listings: list):
        pass
