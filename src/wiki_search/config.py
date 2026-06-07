import os
from pathlib import Path
from dataclasses import dataclass


@dataclass
class WikiSearchConfig:
    include_paths: list[Path]
    index_path: Path
    watch: bool
    reindex_on_start: bool
    host: str = "127.0.0.1"
    port: int = 8765
    embedding_enabled: bool = True
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_device: str = "cpu"

    @classmethod
    def from_env(cls) -> "WikiSearchConfig":
        raw = os.environ.get("WIKI_INCLUDE", "").strip()
        if raw:
            paths = [Path(p.strip()).resolve() for p in raw.split(":") if p.strip()]
        else:
            paths = [Path(os.environ.get("WIKI_ROOT", "./wiki")).resolve()]

        data_dir = Path(os.environ.get("WIKI_DATA_DIR", "./.wiki-index")).resolve()
        return cls(
            include_paths=paths,
            index_path=(data_dir / "wiki.sqlite").resolve(),
            watch=os.environ.get("WIKI_WATCH", "true").lower() in ("true", "1", "yes"),
            reindex_on_start=os.environ.get("WIKI_REINDEX_ON_START", "true").lower() in ("true", "1", "yes"),
            host=os.environ.get("WIKI_HOST", "127.0.0.1"),
            port=int(os.environ.get("WIKI_PORT", "8765")),
            embedding_enabled=os.environ.get("WIKI_EMBEDDING_ENABLED", "true").lower() in ("true", "1", "yes"),
            embedding_model=os.environ.get("WIKI_EMBEDDING_MODEL", "all-MiniLM-L6-v2"),
            embedding_device=os.environ.get("WIKI_EMBEDDING_DEVICE", "cpu"),
        )

    @property
    def data_dir(self) -> Path:
        return self.index_path.parent

    def get_watch_paths(self) -> list[Path]:
        watched = []
        for p in self.include_paths:
            if p.is_dir():
                watched.append(p)
            elif p.parent.exists():
                watched.append(p.parent)
        return watched
