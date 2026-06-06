from pathlib import Path

from wiki_search.index.indexer import rel_path


def test_index_new_file(wiki_dir, indexer):
    filepath = wiki_dir / "guide.md"
    filepath.write_text("# Guide\n\nThis is a guide.\n\n## Section\n\nContent here.\n")
    result = indexer.index_file(filepath)
    assert result is True

    stored = rel_path(filepath)
    doc = indexer.doc_repo.get_document_by_path(stored)
    assert doc is not None
    assert doc["title"] == "Guide"

    chunks = indexer.chunk_repo.get_chunks_by_heading(stored, "Guide")
    assert len(chunks) >= 1


def test_reindex_unchanged_file(wiki_dir, indexer):
    filepath = wiki_dir / "stable.md"
    filepath.write_text("# Stable\n\nContent.\n")
    assert indexer.index_file(filepath) is True
    assert indexer.index_file(filepath) is False


def test_reindex_modified_file(wiki_dir, indexer):
    filepath = wiki_dir / "evolving.md"
    filepath.write_text("# V1\n\nContent.\n")
    assert indexer.index_file(filepath) is True

    filepath.write_text("# V2\n\nUpdated content.\n")
    assert indexer.index_file(filepath) is True


def test_delete_file(wiki_dir, indexer):
    filepath = wiki_dir / "delete_me.md"
    filepath.write_text("# Delete Me\n\nContent.\n")
    indexer.index_file(filepath)
    stored = rel_path(filepath)
    assert indexer.doc_repo.get_document_by_path(stored) is not None

    indexer.delete_file(filepath)
    assert indexer.doc_repo.get_document_by_path(stored) is None


def test_reindex_changed_only(wiki_dir, indexer):
    (wiki_dir / "a.md").write_text("# A\n\nContent A.\n")
    (wiki_dir / "b.md").write_text("# B\n\nContent B.\n")
    assert indexer.reindex_changed_only() == 2

    (wiki_dir / "a.md").write_text("# A\n\nUpdated content.\n")
    assert indexer.reindex_changed_only() == 1

    assert indexer.doc_repo.count_documents() == 2


def test_rebuild(wiki_dir, indexer):
    (wiki_dir / "x.md").write_text("# X\n\nContent X.\n")
    assert indexer.rebuild() == 1


def test_index_nested_file(wiki_dir, indexer):
    sub = wiki_dir / "sub"
    sub.mkdir()
    filepath = sub / "nested.md"
    filepath.write_text("# Nested\n\nDeep content.\n")
    result = indexer.index_file(filepath)
    assert result is True

    stored = rel_path(filepath)
    doc = indexer.doc_repo.get_document_by_path(stored)
    assert doc is not None
