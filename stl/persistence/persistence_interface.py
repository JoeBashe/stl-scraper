class PersistenceInterface:
    def save(self, query: str, listings: list):
        raise NotImplementedError()
