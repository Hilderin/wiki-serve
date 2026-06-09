import sqlite3
from pathlib import Path


class DatabaseManager:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._conn: sqlite3.Connection | None = None

    vec_available: bool = False

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._conn.row_factory = sqlite3.Row
            self._enable_vec()
        return self._conn

    def _enable_vec(self) -> None:
        try:
            import sqlite_vec
            sqlite_vec.load(self._conn)
            self.vec_available = True
        except Exception:
            self.vec_available = False

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None
