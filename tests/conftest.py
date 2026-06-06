import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock

from wiki_search.config import WikiSearchConfig
from wiki_search.db.connection import DatabaseManager
from wiki_search.db.schema import initialize_database
from wiki_search.index.indexer import Indexer
from wiki_search.search.exact_search import ExactSearcher
from wiki_search.search.hybrid_search import HybridSearcher


@pytest.fixture
def tmp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield Path(d)


@pytest.fixture
def wiki_dir(tmp_dir):
    d = tmp_dir / "wiki"
    d.mkdir()
    yield d


@pytest.fixture
def config(tmp_dir, wiki_dir):
    return WikiSearchConfig(
        include_paths=[wiki_dir],
        index_path=tmp_dir / ".wiki-index" / "wiki.sqlite",
        watch=False,
        reindex_on_start=False,
    )


@pytest.fixture
def db(config):
    config.index_path.parent.mkdir(parents=True, exist_ok=True)
    db = DatabaseManager(config.index_path)
    initialize_database(db)
    yield db
    db.close()


def _deterministic_vec(text: str) -> list[float]:
    h = hash(text) & 0xFFFFFFFF
    vec = [0.0] * 384
    idx = h % 384
    vec[idx] = 1.0
    return vec


@pytest.fixture
def mock_embedder():
    embedder = Mock()
    embedder.embed.side_effect = lambda text: _deterministic_vec(text)
    embedder.embed_batch.side_effect = lambda texts: [_deterministic_vec(t) for t in texts]
    embedder.dimension = 384
    return embedder


@pytest.fixture
def indexer(db, config, mock_embedder):
    return Indexer(db, config, embedder=mock_embedder)


@pytest.fixture
def searcher(db):
    return ExactSearcher(db)


@pytest.fixture
def hybrid_searcher(db, mock_embedder):
    return HybridSearcher(db, embedder=mock_embedder)
