from ..db.repository import ChunkRepository


class ExactSearcher:
    def __init__(self, db):
        self.db = db
        self.chunk_repo = ChunkRepository(db)

    def search(self, query: str, limit: int = 10) -> list[dict]:
        if not query.strip():
            return []
        return self.chunk_repo.search_fts(query, limit)
