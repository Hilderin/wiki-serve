import struct
from typing import Any


class DocumentRepository:
    def __init__(self, db):
        self.db = db

    def upsert_document(self, path: str, title: str, content_hash: str, mtime: float, size: int) -> int:
        conn = self.db.conn
        existing = conn.execute(
            "SELECT id FROM documents WHERE path = ?", (path,)
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE documents SET hash = ?, mtime = ?, size = ?, indexed_at = datetime('now') WHERE id = ?",
                (content_hash, mtime, size, existing["id"]),
            )
            return existing["id"]
        cursor = conn.execute(
            "INSERT INTO documents (path, title, hash, mtime, size) VALUES (?, ?, ?, ?, ?)",
            (path, title, content_hash, mtime, size),
        )
        return cursor.lastrowid

    def delete_document(self, path: str) -> None:
        conn = self.db.conn
        doc = conn.execute("SELECT id FROM documents WHERE path = ?", (path,)).fetchone()
        if doc:
            if self.db.vec_available:
                conn.execute("DELETE FROM chunks_vectors WHERE chunk_id IN (SELECT id FROM chunks WHERE document_id = ?)", (doc["id"],))
            conn.execute("DELETE FROM chunks WHERE document_id = ?", (doc["id"],))
            conn.execute("DELETE FROM documents WHERE id = ?", (doc["id"],))

    def delete_documents_by_prefix(self, prefix: str) -> int:
        conn = self.db.conn
        norm_prefix = prefix.replace("\\", "/").rstrip("/") + "/"
        docs = conn.execute(
            "SELECT id, path FROM documents"
        ).fetchall()
        matching = [d["id"] for d in docs if d["path"].replace("\\", "/").startswith(norm_prefix)]
        if not matching:
            return 0
        placeholders = ",".join("?" * len(matching))
        if self.db.vec_available:
            conn.execute(
                f"DELETE FROM chunks_vectors WHERE chunk_id IN (SELECT id FROM chunks WHERE document_id IN ({placeholders}))",
                matching,
            )
        conn.execute(
            f"DELETE FROM chunks_fts WHERE rowid IN (SELECT id FROM chunks WHERE document_id IN ({placeholders}))",
            matching,
        )
        conn.execute(
            f"DELETE FROM chunks WHERE document_id IN ({placeholders})",
            matching,
        )
        conn.execute(
            f"DELETE FROM documents WHERE id IN ({placeholders})",
            matching,
        )
        return len(matching)

    def get_document_by_path(self, path: str) -> dict[str, Any] | None:
        row = self.db.conn.execute(
            "SELECT * FROM documents WHERE path = ?", (path,)
        ).fetchone()
        return dict(row) if row else None

    def get_all_documents(self) -> list[dict[str, Any]]:
        rows = self.db.conn.execute("SELECT * FROM documents").fetchall()
        return [dict(r) for r in rows]

    def count_documents(self) -> int:
        row = self.db.conn.execute("SELECT COUNT(*) as cnt FROM documents").fetchone()
        return row["cnt"]

    def count_chunks(self) -> int:
        row = self.db.conn.execute("SELECT COUNT(*) as cnt FROM chunks").fetchone()
        return row["cnt"]


class ChunkRepository:
    def __init__(self, db):
        self.db = db

    def delete_chunks_for_document(self, document_id: int) -> None:
        conn = self.db.conn
        chunk_ids = conn.execute(
            "SELECT id FROM chunks WHERE document_id = ?", (document_id,)
        ).fetchall()
        for cid in chunk_ids:
            conn.execute("DELETE FROM chunks_fts WHERE rowid = ?", (cid["id"],))
        conn.execute("DELETE FROM chunks WHERE document_id = ?", (document_id,))

    def insert_chunk(
        self,
        document_id: int,
        path: str,
        heading_path: str | None,
        heading_level: int,
        content: str,
        content_hash: str,
        start_line: int,
        end_line: int,
    ) -> int:
        conn = self.db.conn
        cursor = conn.execute(
            "INSERT INTO chunks (document_id, path, heading_path, heading_level, content, content_hash, start_line, end_line) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (document_id, path, heading_path, heading_level, content, content_hash, start_line, end_line),
        )
        chunk_id = cursor.lastrowid
        conn.execute(
            "INSERT INTO chunks_fts (rowid, content, heading_path, path) VALUES (?, ?, ?, ?)",
            (chunk_id, content, heading_path or "", path),
        )
        return chunk_id

    def get_chunks_by_heading(self, path: str, heading_path: str) -> list[dict[str, Any]]:
        rows = self.db.conn.execute(
            "SELECT * FROM chunks WHERE path = ? AND heading_path = ? ORDER BY start_line",
            (path, heading_path),
        ).fetchall()
        return [dict(r) for r in rows]

    def document_has_embeddings(self, document_id: int) -> bool:
        if not self.db.vec_available:
            return False
        row = self.db.conn.execute(
            """SELECT 1 FROM chunks c
               LEFT JOIN chunks_vectors v ON v.chunk_id = c.id
               WHERE c.document_id = ? AND v.chunk_id IS NULL
               LIMIT 1""",
            (document_id,),
        ).fetchone()
        return row is None

    def get_chunk_ids_for_document(self, document_id: int) -> list[int]:
        rows = self.db.conn.execute(
            "SELECT id FROM chunks WHERE document_id = ?", (document_id,)
        ).fetchall()
        return [r["id"] for r in rows]

    def insert_embedding(self, chunk_id: int, embedding: list[float]) -> None:
        if not self.db.vec_available:
            return
        vec = struct.pack(f"{len(embedding)}f", *embedding)
        self.db.conn.execute(
            "INSERT OR REPLACE INTO chunks_vectors (chunk_id, embedding) VALUES (?, ?)",
            (chunk_id, vec),
        )

    def delete_embeddings_for_document(self, document_id: int) -> None:
        if not self.db.vec_available:
            return
        conn = self.db.conn
        chunk_ids = conn.execute(
            "SELECT id FROM chunks WHERE document_id = ?", (document_id,)
        ).fetchall()
        for cid in chunk_ids:
            conn.execute("DELETE FROM chunks_vectors WHERE chunk_id = ?", (cid["id"],))

    def search_vector(self, embedding: list[float], limit: int = 10) -> list[dict[str, Any]]:
        if not self.db.vec_available:
            return []
        vec = struct.pack(f"{len(embedding)}f", *embedding)
        rows = self.db.conn.execute(
            """SELECT c.id, c.path, c.heading_path, c.heading_level, c.content,
                      c.start_line, c.end_line, distance
               FROM chunks_vectors
               JOIN chunks c ON chunks_vectors.chunk_id = c.id
               WHERE embedding MATCH ? AND k = ?""",
            (vec, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def search_fts(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        fts_query = self._prepare_query(query)
        if not fts_query:
            return []
        rows = self.db.conn.execute(
            """SELECT c.id, c.path, c.heading_path, c.heading_level, c.content,
                      c.start_line, c.end_line, rank AS bm25
               FROM chunks_fts
               JOIN chunks c ON chunks_fts.rowid = c.id
               WHERE chunks_fts MATCH ?
               ORDER BY rank
               LIMIT ?""",
            (fts_query, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def _prepare_query(self, query: str) -> str:
        query = query.strip()
        if not query:
            return ""
        if any(op in query for op in ('"', "'", "(", ")", "*", "NEAR", "AND", "OR", "NOT")):
            return query
        terms = query.split()
        if not terms:
            return ""
        return " AND ".join(f'"{t}"' for t in terms)
