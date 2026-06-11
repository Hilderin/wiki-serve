import hashlib
from datetime import datetime
from pathlib import Path

from ..config import WikiSearchConfig
from ..db.repository import DocumentRepository, ChunkRepository
from ..search.embedder import Embedder
from . import markdown_chunker as chunker

_cwd = Path.cwd()

_DEFAULT_SKIP_NAMES = frozenset(s.lower() for s in {
    "node_modules", ".git", ".venv", "__pycache__", "tmp", "temp",
    ".ds_store", "thumbs.db", "desktop.ini", "agents.md",
})


def rel_path(filepath: Path) -> str:
    fp = filepath.resolve()
    try:
        return str(fp.relative_to(_cwd))
    except ValueError:
        return str(fp)


class Indexer:
    def __init__(self, db, config: WikiSearchConfig, embedder: Embedder | None = None):
        self.db = db
        self.config = config
        self.doc_repo = DocumentRepository(db)
        self.chunk_repo = ChunkRepository(db)
        self.embedder = embedder
        self._log_path = config.data_dir / "wiki.indexation.log"
        self._log("STARTUP", f"Indexer initialized (paths={config.include_paths})")
        for p in config.skipped_paths:
            self._log("WARNING", f"Include path does not exist, skipping: {p}")

        self._skip_names: set[str] = set(_DEFAULT_SKIP_NAMES)
        self._skip_dotfiles = True
        self._allow_dot_names: set[str] = set()

        for p in config.exclude_patterns:
            if p == "!.*":
                self._skip_dotfiles = False
            elif p.startswith("!."):
                self._allow_dot_names.add(p[1:].lower())
            elif p.startswith("!"):
                self._skip_names.discard(p[1:].lower())
            else:
                self._skip_names.add(p.lower())

    def _log(self, level: str, message: str) -> None:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        line = f"{ts} | {level:7s} | {message}"
        try:
            self._log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._log_path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError as e:
            print(f"[wiki-serve] LOG WRITE FAILED ({e}): {line}", flush=True)
        if level in ("INDEXING", "VECTORS", "INDEXED", "VECTORED", "DELETED", "REMOVED", "SKIPPED", "REINDEX", "REBUILD", "STARTUP", "UP-TO-DATE", "WARNING", "ERROR"):
            print(f"[wiki-serve] {line}", flush=True)

    def index_file(self, filepath: Path) -> bool:
        filepath = filepath.resolve()
        path_str = rel_path(filepath)

        content = None
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                content = filepath.read_text(encoding=enc)
                break
            except (UnicodeDecodeError, UnicodeError):
                continue
        if content is None:
            raise UnicodeDecodeError("unknown", b"", 0, 1, "unable to decode file with any supported encoding")
        mtime = filepath.stat().st_mtime
        size = len(content.encode("utf-8"))
        content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]

        with self.db.lock:
            existing = self.doc_repo.get_document_by_path(path_str)
            if existing and existing["hash"] == content_hash:
                if self.embedder is not None and self.db.vec_available and not self.chunk_repo.document_has_embeddings(existing["id"]):
                    self._log("VECTORS", f"Adding missing embeddings: {path_str}")
                    chunk_ids = self.chunk_repo.get_chunk_ids_for_document(existing["id"])
                    chunk_contents = []
                    for cid in chunk_ids:
                        row = self.db.conn.execute(
                            "SELECT content FROM chunks WHERE id = ?", (cid,)
                        ).fetchone()
                        chunk_contents.append((cid, row["content"]))
                    embeddings = self.embedder.embed_batch([c for _, c in chunk_contents])
                    for (cid, _), emb in zip(chunk_contents, embeddings):
                        self.chunk_repo.insert_embedding(cid, emb)
                    self.db.conn.commit()
                    self._log("VECTORED", path_str)
                    return True
                self._log("UP-TO-DATE", path_str)
                return False

            self._log("INDEXING", path_str)

            title = _extract_title(content, path_str)

            conn = self.db.conn
            doc_id = self.doc_repo.upsert_document(path_str, title, content_hash, mtime, size)
            self.chunk_repo.delete_chunks_for_document(doc_id)

            chunks = chunker.chunk_content(path_str, content.split("\n"))
            embed_texts = []
            for ch in chunks:
                ch["path"] = path_str
                if not ch["heading_path"]:
                    ch["heading_path"] = title or path_str
                    ch["heading_level"] = 0

            if self.embedder is not None:
                embed_texts = [ch["content"] for ch in chunks]

            for ch in chunks:
                chunk_id = self.chunk_repo.insert_chunk(
                    doc_id, ch["path"], ch["heading_path"],
                    ch["heading_level"], ch["content"],
                    ch["content_hash"], ch["start_line"], ch["end_line"],
                )
                ch["_chunk_id"] = chunk_id

            if self.embedder is not None and embed_texts:
                embeddings = self.embedder.embed_batch(embed_texts)
                for ch, emb in zip(chunks, embeddings):
                    self.chunk_repo.insert_embedding(ch["_chunk_id"], emb)

            conn.commit()
            self._log("INDEXED", path_str)
        return True

    def delete_file(self, filepath: Path) -> None:
        path_str = rel_path(filepath)
        with self.db.lock:
            self.doc_repo.delete_document(path_str)
            self.db.conn.commit()
        self._log("DELETED", path_str)

    def delete_directory(self, dirpath: Path) -> int:
        prefix = rel_path(dirpath)
        with self.db.lock:
            count = self.doc_repo.delete_documents_by_prefix(prefix)
            if count:
                self.db.conn.commit()
        if count:
            self._log("REMOVED", f"Deleted directory ({count} documents): {prefix}")
        return count

    def _should_skip(self, path: Path, root: Path | None = None) -> bool:
        if path.name.lower() in self._skip_names:
            return True
        if root is not None:
            try:
                check = path.resolve().relative_to(root.resolve()).parts
            except ValueError:
                check = path.parts
        else:
            check = path.parts
        for part in check:
            part_lower = part.lower()
            if part_lower in self._skip_names:
                return True
            if self._skip_dotfiles and part.startswith(".") and part_lower not in self._allow_dot_names:
                return True
        return False

    def _collect_md_files(self) -> list[Path]:
        files: list[Path] = []
        for path in self.config.include_paths:
            p = path.resolve()
            if p.is_file():
                if p.suffix == ".md" and not self._should_skip(p):
                    files.append(p)
            elif p.is_dir():
                files.extend(f for f in sorted(p.rglob("*.md")) if not self._should_skip(f, root=p))
        return files

    def reindex_changed_only(self) -> int:
        self._log("REINDEX", "Starting changed-only reindex")
        md_files = self._collect_md_files()

        if not md_files:
            self._log("REINDEX", "No markdown files found in include paths")
            return 0

        count = 0
        errors = 0
        for filepath in md_files:
            try:
                if self.index_file(filepath):
                    count += 1
            except Exception as exc:
                errors += 1
                self._log("ERROR", f"Failed to index {filepath}: {exc}")

        indexed_set = {rel_path(f) for f in md_files}
        removed_count = 0
        skipped_count = 0
        for doc in self.doc_repo.get_all_documents():
            if doc["path"] in indexed_set:
                continue
            doc_path = _cwd / doc["path"]
            doc_root = None
            for ip in self.config.include_paths:
                try:
                    doc_path.resolve().relative_to(ip.resolve())
                    doc_root = ip.resolve()
                    break
                except ValueError:
                    continue
            if doc_path.exists() and self._should_skip(doc_path, root=doc_root):
                self._log("SKIPPED", f"Removing skipped document: {doc['path']}")
                skipped_count += 1
            elif not doc_path.exists():
                self._log("REMOVED", f"Removing deleted document: {doc['path']}")
                removed_count += 1
            else:
                self._log("STALE", f"Removing stale document: {doc['path']}")
            self.doc_repo.delete_document(doc["path"])

        self.db.conn.commit()
        removed_summary = ""
        if removed_count or skipped_count:
            parts = []
            if removed_count:
                parts.append(f"{removed_count} removed")
            if skipped_count:
                parts.append(f"{skipped_count} skipped")
            removed_summary = f", {', '.join(parts)}"
        if errors:
            self._log("REINDEX", f"Completed: {len(md_files)} files scanned, {count} reindexed{removed_summary}, {errors} errors")
        else:
            self._log("REINDEX", f"Completed: {len(md_files)} files scanned, {count} reindexed{removed_summary}")
        return count

    def rebuild(self) -> int:
        self._log("REBUILD", "Starting full rebuild")
        conn = self.db.conn
        if self.db.vec_available:
            conn.execute("DELETE FROM chunks_vectors")
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
