SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT UNIQUE NOT NULL,
    title TEXT,
    hash TEXT NOT NULL,
    mtime REAL NOT NULL,
    size INTEGER NOT NULL,
    indexed_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS chunks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL,
    path TEXT NOT NULL,
    heading_path TEXT,
    heading_level INTEGER,
    content TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    start_line INTEGER,
    end_line INTEGER,
    FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
);

CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    content,
    heading_path,
    path
);

"""


VEC_SCHEMA_SQL = """
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_vectors USING vec0(
    chunk_id INTEGER PRIMARY KEY,
    embedding FLOAT[384]
);
"""


def initialize_database(db) -> None:
    db.conn.executescript(SCHEMA_SQL)
    if db.vec_available:
        db.conn.executescript(VEC_SCHEMA_SQL)
    db.conn.commit()
