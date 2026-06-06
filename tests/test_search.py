import pytest

from wiki_search.index.indexer import rel_path


def test_search_empty(wiki_dir, indexer, searcher):
    results = searcher.search("nothing")
    assert results == []


def test_search_basic(wiki_dir, indexer, searcher):
    filepath = wiki_dir / "doc.md"
    filepath.write_text("# Document\n\nThis is important content about agents.\n")
    indexer.reindex_changed_only()

    results = searcher.search("agents")
    assert len(results) >= 1
    assert results[0]["path"] == rel_path(filepath)


def test_search_no_results(wiki_dir, indexer, searcher):
    (wiki_dir / "doc.md").write_text("# Document\n\nSome content.\n")
    indexer.reindex_changed_only()

    results = searcher.search("xyznonexistent")
    assert results == []


def test_search_multiple_terms(wiki_dir, indexer, searcher):
    a = wiki_dir / "a.md"
    a.write_text("# Architecture\n\nAgents handle handoff.\n")
    b = wiki_dir / "b.md"
    b.write_text("# Backup\n\nBackup configuration.\n")
    indexer.reindex_changed_only()

    results = searcher.search("agents handoff")
    assert any(r["path"] == rel_path(a) for r in results)


def test_read_section(wiki_dir, indexer, db):
    filepath = wiki_dir / "doc.md"
    filepath.write_text("# Title\n\n## Section\n\nSpecific content here.\n\n## Other\n\nOther content.\n")
    indexer.reindex_changed_only()

    from wiki_search.db.repository import ChunkRepository
    repo = ChunkRepository(db)
    chunks = repo.get_chunks_by_heading(rel_path(filepath), "Title > Section")
    assert len(chunks) >= 1
    assert "Specific content" in chunks[0]["content"]


def test_status(wiki_dir, indexer, db, config):
    from wiki_search.db.repository import DocumentRepository
    repo = DocumentRepository(db)

    (wiki_dir / "status.md").write_text("# Status\n\nContent.\n")
    indexer.reindex_changed_only()

    assert repo.count_documents() == 1
    assert repo.count_chunks() >= 1
    assert config.watch is False


@pytest.mark.parametrize("query,expected", [
    ("agents", True),
    ("Architecture", True),
    ("handoff", True),
])
def test_search_parametrized(wiki_dir, indexer, searcher, query, expected):
    filepath = wiki_dir / "doc.md"
    filepath.write_text("# Architecture\n\nAgents handle handoff between components.\n")
    indexer.reindex_changed_only()

    results = searcher.search(query)
    if expected:
        assert len(results) >= 1
    else:
        assert len(results) == 0
