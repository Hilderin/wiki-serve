import pytest
import tempfile
from pathlib import Path

from wiki_search.config import WikiSearchConfig
from wiki_search.db.connection import DatabaseManager
from wiki_search.db.schema import initialize_database
from wiki_search.index.indexer import Indexer
from wiki_search.search.exact_search import ExactSearcher


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


@pytest.fixture
def indexer(db, config):
    return Indexer(db, config)


@pytest.fixture
def searcher(db):
    return ExactSearcher(db)
