import os
import sys
from pathlib import Path
from dataclasses import dataclass, field


@dataclass
class WikiSearchConfig:
    include_paths: list[Path]
    skipped_paths: list[Path] = field(default_factory=list)
    exclude_patterns: list[str] = field(default_factory=list)
    index_path: Path = Path("./.wiki-index/wiki.sqlite").resolve()
    watch: bool = True
    reindex_on_start: bool = True
    host: str = "127.0.0.1"
    port: int = 8765
    embedding_enabled: bool = True
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_device: str = "cpu"

    @classmethod
    def from_env(cls) -> "WikiSearchConfig":
        raw = os.environ.get("WIKI_INCLUDE", "").strip()
        if raw:
            all_paths = [Path(p.strip()).resolve() for p in raw.split(";") if p.strip()]
        else:
            all_paths = [Path(os.environ.get("WIKI_ROOT", "./wiki")).resolve()]

        valid_paths: list[Path] = []
        skipped_paths: list[Path] = []
        for p in all_paths:
            if p.exists():
                valid_paths.append(p)
            else:
                skipped_paths.append(p)
                msg = f"[wiki-serve] WARNING: Include path does not exist, skipping: {p}"
                print(msg, file=sys.stderr, flush=True)

        raw_exclude = os.environ.get("WIKI_EXCLUDE", "").strip()
        exclude_patterns = [p.strip() for p in raw_exclude.split(";") if p.strip()] if raw_exclude else []

        data_dir = Path(os.environ.get("WIKI_DATA_DIR", "./.wiki-index")).resolve()
        return cls(
            include_paths=valid_paths,
            skipped_paths=skipped_paths,
            exclude_patterns=exclude_patterns,
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
