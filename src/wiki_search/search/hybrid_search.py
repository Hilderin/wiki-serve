from .exact_search import ExactSearcher


class HybridSearcher:
    def __init__(self, db):
        self.db = db
        self.exact = ExactSearcher(db)

    def search(self, query: str, limit: int = 10) -> list[dict]:
        return self.exact.search(query, limit)
