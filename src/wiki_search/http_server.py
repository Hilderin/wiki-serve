import sys
from pathlib import Path

import anyio
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader, select_autoescape

from mcp.server.fastmcp import FastMCP

from . import __version__
from .mcp_tools.read_section import read_section_from_disk
from .config import WikiSearchConfig
from .db.connection import DatabaseManager
from .db.schema import initialize_database
from .index.indexer import Indexer
from .search.hybrid_search import HybridSearcher
from .search.exact_search import ExactSearcher
from .search.embedder import Embedder
from .search.rank import normalize_bm25_score, rerank_with_heading_boost
from .db.repository import DocumentRepository, ChunkRepository
from .index.watcher import start_watcher


TEMPLATES_DIR = Path(__file__).parent / "web" / "templates"
STATIC_DIR = Path(__file__).parent / "web" / "static"

_jinja = Environment(
    loader=FileSystemLoader(str(TEMPLATES_DIR)),
    autoescape=select_autoescape(["html"]),
)


def _render(name: str, **kwargs) -> str:
    return _jinja.get_template(name).render(**kwargs)


def _make_vscode_url():
    cwd = Path.cwd()
    def helper(path: str, line: int = 1) -> str:
        full = (cwd / path).resolve()
        return f"vscode://file/{full}:{line}"
    return helper


def _format_search_result(r: dict) -> dict:
    score = r.get("score") or normalize_bm25_score(r.pop("bm25", 0))
    excerpt = (r.get("content") or "")[:300].replace("\n", " ")
    vscode = _make_vscode_url()
    return {
        "path": r["path"],
        "heading_path": r.get("heading_path"),
        "score": score,
        "excerpt": excerpt,
        "start_line": r["start_line"],
        "end_line": r["end_line"],
        "vscode_url": vscode(r["path"], r["start_line"]),
        "content": r.get("content", ""),
    }


def create_app(config: WikiSearchConfig | None = None) -> FastAPI:
    if config is None:
        config = WikiSearchConfig.from_env()
    config.data_dir.mkdir(parents=True, exist_ok=True)

    db = DatabaseManager(config.index_path)
    initialize_database(db)

    embedder = Embedder(config.embedding_model, config.embedding_device) if config.embedding_enabled else None
    if embedder is not None:
        embedder.load()
    indexer = Indexer(db, config, embedder=embedder)
    if config.reindex_on_start:
        indexer.reindex_changed_only()

    observer = None
    if config.watch:
        observer = start_watcher(config, indexer)

    hybrid = HybridSearcher(db, embedder=embedder)
    exact = ExactSearcher(db)
    doc_repo = DocumentRepository(db)
    chunk_repo = ChunkRepository(db)

    mcp = FastMCP("wiki-serve")

    @mcp.tool()
    def search(query: str, limit: int = 10) -> str:
        results = hybrid.search(query, limit)
        for r in results:
            if "bm25" in r:
                r["score"] = normalize_bm25_score(r.pop("bm25"))
        results = rerank_with_heading_boost(results, query)
        lines = [f"Query: {query} | Results: {len(results)}"]
        for r in results:
            heading = r.get("heading_path") or ""
            excerpt = (r.get("content") or "")[:200].replace("\n", " ")
            lines.append(f"  [{r['score']:.2f}] {r['path']} | {heading} | L{r['start_line']}-{r['end_line']}")
            lines.append(f"    {excerpt}")
        return "\n".join(lines)

    @mcp.tool()
    def search_exact(query: str, limit: int = 10) -> str:
        results = exact.search(query, limit)
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
        return "\n".join(lines)

    @mcp.tool()
    def read_section(path: str, heading: str) -> str:
        section = read_section_from_disk(config, path, heading)
        if section:
            return (
                f"File: {path}\n"
                f"Heading: {heading}\n"
                f"Lines: {section['start_line']}-{section['end_line']}\n\n"
                f"{section['content']}"
            )

        chunks = chunk_repo.get_chunks_by_heading(path, heading)
        if not chunks:
            return f"Section not found: '{heading}' in '{path}'"
        content = "\n".join(c["content"] for c in chunks)
        return (
            f"File: {path}\n"
            f"Heading: {heading}\n"
            f"Lines: {chunks[0]['start_line']}-{chunks[-1]['end_line']}\n"
            f"(partial content — file not available on disk)\n\n"
            f"{content}"
        )

    app = FastAPI(title="Wiki Serve", version=__version__)

    if observer is not None:
        @app.on_event("shutdown")
        async def _stop_watcher():
            observer.stop()
            observer.join()

    sse_app = mcp.sse_app()
    app.mount("/mcp", sse_app)

    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/", response_class=HTMLResponse)
    async def index_page(q: str | None = Query(default=None)):
        results_data = []
        if q:
            raw = hybrid.search(q)
            for r in raw:
                results_data.append(_format_search_result(r))
            results_data = rerank_with_heading_boost(results_data, q)
        return _render("index.html", query=q or "", results=results_data, vscode_url=_make_vscode_url())

    @app.get("/api/search")
    async def api_search(q: str = Query(default=""), limit: int = Query(default=20)):
        if not q.strip():
            return JSONResponse({"results": []})
        raw = hybrid.search(q, limit)
        results = [_format_search_result(r) for r in raw]
        results = rerank_with_heading_boost(results, q)
        return JSONResponse({"query": q, "results": results})

    @app.get("/section", response_class=HTMLResponse)
    async def section_page(path: str = Query(default=""), heading: str = Query(default=""), q: str | None = Query(default=None)):
        section = read_section_from_disk(config, path, heading)
        if section:
            return _render("section.html", path=path, heading=heading, content=section["content"], start_line=section["start_line"], end_line=section["end_line"], query=q, vscode_url=_make_vscode_url())

        chunks = chunk_repo.get_chunks_by_heading(path, heading)
        if not chunks:
            return _render("section.html", path=path, heading=heading, content="Section not found.", start_line=0, end_line=0, query=q, vscode_url=_make_vscode_url())
        content = "\n".join(c["content"] for c in chunks)
        return _render("section.html", path=path, heading=heading, content=content, start_line=chunks[0]["start_line"], end_line=chunks[-1]["end_line"], query=q, vscode_url=_make_vscode_url())

    @app.get("/status", response_class=HTMLResponse)
    async def status_page():
        row = db.conn.execute("SELECT MAX(indexed_at) as last_indexed FROM documents").fetchone()
        log_path = config.data_dir / "wiki.indexation.log"
        return _render("status.html",
            doc_count=doc_repo.count_documents(),
            chunk_count=doc_repo.count_chunks(),
            last_indexed=row["last_indexed"] if row else "never",
            watcher="enabled" if config.watch else "disabled",
            include_paths=[str(p) for p in config.include_paths],
            data_path=str(config.index_path),
            log_path=str(log_path),
        )

    @app.get("/api/status")
    async def api_status():
        row = db.conn.execute("SELECT MAX(indexed_at) as last_indexed FROM documents").fetchone()
        log_path = config.data_dir / "wiki.indexation.log"
        return JSONResponse({
            "documents": doc_repo.count_documents(),
            "chunks": doc_repo.count_chunks(),
            "last_indexed": row["last_indexed"] if row else None,
            "watcher": config.watch,
            "include_paths": [str(p) for p in config.include_paths],
            "data_path": str(config.index_path),
            "log_path": str(log_path),
        })

    @app.post("/api/reindex")
    async def api_reindex(mode: str = Query(default="changed-only")):
        if mode == "rebuild":
            count = indexer.rebuild()
            return JSONResponse({"status": "ok", "message": f"Rebuilt index: {count} files indexed"})
        count = indexer.reindex_changed_only()
        return JSONResponse({"status": "ok", "message": f"Reindexed {count} files"})

    @app.get("/health")
    async def health():
        return JSONResponse({"status": "ok", "version": __version__})

    return app


def run(config: WikiSearchConfig | None = None) -> None:
    if config is None:
        config = WikiSearchConfig.from_env()
    import uvicorn
    uvicorn.run(
        "wiki_search.http_server:create_app",
        host=config.host,
        port=config.port,
        factory=True,
        log_level="info",
    )
