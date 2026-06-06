from .exact_search import ExactSearcher
from .embedder import Embedder
from ..db.repository import ChunkRepository
from .rank import rrf_fuse


class HybridSearcher:
    def __init__(self, db, embedder: Embedder | None = None):
        self.db = db
        self.exact = ExactSearcher(db)
        self.chunk_repo = ChunkRepository(db)
        self.embedder = embedder

    def search(self, query: str, limit: int = 10) -> list[dict]:
        if not query.strip():
            return []

        fts_results = self.exact.search(query, limit * 2)

        if self.embedder is not None:
            query_vec = self.embedder.embed(query)
            vec_results = self.chunk_repo.search_vector(query_vec, limit * 2)
            return rrf_fuse(fts_results, vec_results, limit)
        else:
            return fts_results
