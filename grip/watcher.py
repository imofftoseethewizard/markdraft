"""
File change watcher for auto-refresh.
"""

import time
import threading
from typing import Generator

from .readers import ReadmeReader


class FileWatcher:
    """Polls a reader for file changes."""

    def __init__(self, reader: ReadmeReader, subpath: str | None = None,
                 interval: float = 0.3) -> None:
        self.reader = reader
        self.subpath = subpath
        self.interval = interval

    def watch(self, shutdown_event: threading.Event) -> Generator[bool, None, None]:
        """Generator that yields True when the watched file changes.

        Blocks between polls. Exits when shutdown_event is set.
        """
        last_updated = self.reader.last_updated(self.subpath)
        while not shutdown_event.is_set():
            time.sleep(self.interval)
            updated = self.reader.last_updated(self.subpath)
            if updated != last_updated:
                last_updated = updated
                yield True
