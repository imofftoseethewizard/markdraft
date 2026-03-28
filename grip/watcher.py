"""
File change watcher for auto-refresh.
"""

import time


class FileWatcher:
    """Polls a reader for file changes."""

    def __init__(self, reader, subpath=None, interval=0.3):
        self.reader = reader
        self.subpath = subpath
        self.interval = interval

    def watch(self, shutdown_event):
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
