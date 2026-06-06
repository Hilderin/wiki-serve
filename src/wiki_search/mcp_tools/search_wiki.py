from mcp.types import Tool, TextContent

from ..search.rank import normalize_bm25_score, rerank_with_heading_boost

SEARCH_WIKI_TOOL = Tool(
    name="wiki_search",
    description="Search the wiki using hybrid (FTS + semantic) search. Use for conceptual or fuzzy project questions.",
    inputSchema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"},
            "limit": {"type": "integer", "description": "Maximum number of results", "default": 10},
        },
        "required": ["query"],
    },
)

SEARCH_EXACT_TOOL = Tool(
    name="wiki_search_exact",
    description="Search the wiki using exact lexical/FTS search. Use for specific terms, IDs, file names, class names.",
    inputSchema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "Search query"},
            "limit": {"type": "integer", "description": "Maximum number of results", "default": 10},
        },
        "required": ["query"],
    },
)


async def handle_search(searcher, arguments: dict) -> list[TextContent]:
    query = arguments["query"]
    limit = arguments.get("limit", 10)
    results = searcher.search(query, limit)
    return _format_results(query, results)


async def handle_search_exact(searcher, arguments: dict) -> list[TextContent]:
    query = arguments["query"]
    limit = arguments.get("limit", 10)
    results = searcher.search(query, limit)
    return _format_results(query, results)


def _format_results(query: str, results: list[dict]) -> list[TextContent]:
    for r in results:
        bm25 = r.pop("bm25", 0)
        r["score"] = normalize_bm25_score(bm25)

    results = rerank_with_heading_boost(results, query)

    lines = [f"Query: {query} | Results: {len(results)}"]
    for r in results:
        heading = r.get("heading_path") or ""
        excerpt = (r.get("content") or "")[:200].replace("\n", " ")
        lines.append(f"  [{r['score']:.2f}] {r['path']} | {heading} | L{r['start_line']}-{r['end_line']}")
        lines.append(f"    {excerpt}")

    return [TextContent(type="text", text="\n".join(lines))]
