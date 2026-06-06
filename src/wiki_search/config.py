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

    @classmethod
    def from_env(cls) -> "WikiSearchConfig":
        raw = os.environ.get("WIKI_INCLUDE", "").strip()
        if raw:
            paths = [Path(p.strip()).resolve() for p in raw.split(":") if p.strip()]
        else:
            paths = [Path(os.environ.get("WIKI_ROOT", "./wiki")).resolve()]
        return cls(
            include_paths=paths,
            index_path=Path(os.environ.get("WIKI_INDEX", "./.wiki-index/wiki.sqlite")).resolve(),
            watch=os.environ.get("WIKI_WATCH", "true").lower() in ("true", "1", "yes"),
            reindex_on_start=os.environ.get("WIKI_REINDEX_ON_START", "true").lower() in ("true", "1", "yes"),
            host=os.environ.get("WIKI_HOST", "127.0.0.1"),
            port=int(os.environ.get("WIKI_PORT", "8765")),
        )

    def get_watch_paths(self) -> list[Path]:
        watched = []
        for p in self.include_paths:
            if p.is_dir():
                watched.append(p)
            elif p.parent.exists():
                watched.append(p.parent)
        return watched
