import asyncio
import time
from pathlib import Path

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from ..config import WikiSearchConfig
from .indexer import Indexer
from .indexer import rel_path


class WikiEventHandler(FileSystemEventHandler):
    def __init__(self, indexer: Indexer, config: WikiSearchConfig, debounce_seconds: float = 1.0):
        self.indexer = indexer
        self.config = config
        self.debounce_seconds = debounce_seconds
        self._last_event: dict[str, float] = {}

    def on_created(self, event):
        if event.is_directory or not event.src_path.endswith(".md"):
            return
        self._debounce(event.src_path, "created")

    def on_modified(self, event):
        if event.is_directory or not event.src_path.endswith(".md"):
            return
        self._debounce(event.src_path, "modified")

    def on_deleted(self, event):
        if event.is_directory or not event.src_path.endswith(".md"):
            return
        self.indexer.delete_file(Path(event.src_path))

    def on_moved(self, event):
        if event.is_directory or not event.src_path.endswith(".md"):
            return
        self.indexer.delete_file(Path(event.src_path))
        if event.dest_path:
            time.sleep(0.1)
            dest = Path(event.dest_path)
            if dest.exists():
                self.indexer.index_file(dest)

    def _debounce(self, src_path: str, _event_type: str) -> None:
        now = time.time()
        last = self._last_event.get(src_path, 0)
        if now - last < self.debounce_seconds:
            return
        self._last_event[src_path] = now

        filepath = Path(src_path)
        if filepath.exists():
            self.indexer.index_file(filepath)


def start_watcher(config: WikiSearchConfig, indexer: Indexer) -> Observer | None:
    watch_paths = config.get_watch_paths()
    if not watch_paths:
        return None

    handler = WikiEventHandler(indexer, config)
    observer = Observer()
    for wp in watch_paths:
        wp.mkdir(parents=True, exist_ok=True)
        observer.schedule(handler, str(wp), recursive=True)
    observer.start()
    return observer
