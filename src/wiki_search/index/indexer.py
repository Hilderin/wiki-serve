import hashlib
import os
from datetime import datetime
from pathlib import Path

from ..config import WikiSearchConfig
from ..db.repository import DocumentRepository, ChunkRepository
from . import markdown_chunker as chunker

_cwd = Path.cwd()


def rel_path(filepath: Path) -> str:
    fp = filepath.resolve()
    try:
        return str(fp.relative_to(_cwd))
    except ValueError:
        return str(fp)


class Indexer:
    def __init__(self, db, config: WikiSearchConfig):
        self.db = db
        self.config = config
        self.doc_repo = DocumentRepository(db)
        self.chunk_repo = ChunkRepository(db)
        self._log_path = config.index_path.parent / "wiki.indexation.log"
        config.index_path.parent.mkdir(parents=True, exist_ok=True)
        self._log("STARTUP", f"Indexer initialized (paths={config.include_paths})")

    def _log(self, level: str, message: str) -> None:
        try:
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            with open(self._log_path, "a", encoding="utf-8") as f:
                f.write(f"{ts} | {level:7s} | {message}\n")
        except OSError:
            pass

    def index_file(self, filepath: Path) -> bool:
        filepath = filepath.resolve()
        path_str = rel_path(filepath)

        content = filepath.read_text(encoding="utf-8")
        mtime = filepath.stat().st_mtime
        size = len(content.encode("utf-8"))
        content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]

        existing = self.doc_repo.get_document_by_path(path_str)
        if existing and existing["hash"] == content_hash:
            self._log("UP-TO-DATE", path_str)
            return False

        self._log("INDEXING", path_str)

        title = _extract_title(content, path_str)

        conn = self.db.conn
        doc_id = self.doc_repo.upsert_document(path_str, title, content_hash, mtime, size)
        self.chunk_repo.delete_chunks_for_document(doc_id)

        chunks = chunker.chunk_file(filepath)
        for ch in chunks:
            ch["path"] = path_str
            if not ch["heading_path"]:
                ch["heading_path"] = title or path_str
                ch["heading_level"] = 0
            self.chunk_repo.insert_chunk(
                doc_id, ch["path"], ch["heading_path"],
                ch["heading_level"], ch["content"],
                ch["content_hash"], ch["start_line"], ch["end_line"],
            )

        conn.commit()
        self._log("INDEXED", path_str)
        return True

    def delete_file(self, filepath: Path) -> None:
        path_str = rel_path(filepath)
        conn = self.db.conn
        self.doc_repo.delete_document(path_str)
        conn.commit()
        self._log("DELETED", path_str)

    def _collect_md_files(self) -> list[Path]:
        files: list[Path] = []
        for path in self.config.include_paths:
            p = path.resolve()
            if p.is_file():
                if p.suffix == ".md":
                    files.append(p)
            elif p.is_dir():
                files.extend(sorted(p.rglob("*.md")))
        return files

    def reindex_changed_only(self) -> int:
        self._log("REINDEX", "Starting changed-only reindex")
        md_files = self._collect_md_files()

        if not md_files:
            self._log("REINDEX", "No markdown files found in include paths")
            return 0

        count = 0
        for filepath in md_files:
            if self.index_file(filepath):
                count += 1

        indexed_set = {rel_path(f) for f in md_files}
        for doc in self.doc_repo.get_all_documents():
            if doc["path"] not in indexed_set:
                self._log("STALE", f"Removing stale document: {doc['path']}")
                self.doc_repo.delete_document(doc["path"])

        self.db.conn.commit()
        self._log("REINDEX", f"Completed: {len(md_files)} files scanned, {count} reindexed")
        return count

    def rebuild(self) -> int:
        self._log("REBUILD", "Starting full rebuild")
        conn = self.db.conn
        conn.execute("DELETE FROM chunks_fts")
        conn.execute("DELETE FROM chunks")
        conn.execute("DELETE FROM documents")
        conn.commit()
        result = self.reindex_changed_only()
        self._log("REBUILD", f"Full rebuild complete: {result} files indexed")
        return result


def _extract_title(content: str, fallback: str) -> str:
    for line in content.split("\n"):
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
        if stripped.startswith("#") and not stripped.startswith("##"):
            return stripped[1:].strip()
    return fallback
