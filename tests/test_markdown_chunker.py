from wiki_search.index.markdown_chunker import chunk_content


def test_simple_headings():
    lines = [
        "# Architecture",
        "",
        "Content about architecture.",
        "## Agents",
        "Content about agents.",
        "### Handoff",
        "Handoff details.",
    ]
    chunks = chunk_content("test.md", lines)
    assert len(chunks) == 3
    assert chunks[0]["heading_path"] == "Architecture"
    assert chunks[1]["heading_path"] == "Architecture > Agents"
    assert chunks[2]["heading_path"] == "Architecture > Agents > Handoff"


def test_no_headings():
    lines = ["Some content.", "Without headings.", "Just text."]
    chunks = chunk_content("test.md", lines)
    assert len(chunks) == 1
    assert chunks[0]["heading_path"] is None


def test_large_section(tmp_path):
    from wiki_search.index import markdown_chunker as mc
    original = mc.CHUNK_MAX_LINES
    mc.CHUNK_MAX_LINES = 5
    try:
        lines = ["# Big Section"] + [f"Line {i}" for i in range(20)]
        chunks = chunk_content("test.md", lines)
        assert len(chunks) > 1
        assert "Big Section" in chunks[0]["heading_path"]
        for c in chunks:
            assert len(c["content"].split("\n")) <= mc.CHUNK_MAX_LINES
    finally:
        mc.CHUNK_MAX_LINES = original


def test_no_heading_no_title():
    lines = ["Just a line", "Another line"]
    chunks = chunk_content("test.md", lines)
    assert len(chunks) == 1


def test_content_hash_stable():
    lines = ["# Stable", "content"]
    c1 = chunk_content("test.md", lines)
    c2 = chunk_content("test.md", lines)
    assert c1[0]["content_hash"] == c2[0]["content_hash"]
