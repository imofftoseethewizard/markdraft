"""
Asset cache for CDN-fetched JavaScript and CSS libraries.
"""

import os
import shutil
import sys
import urllib.request

from .config import CDN_ASSETS


class AssetCache:
    """Downloads and caches CDN assets in a local directory."""

    def __init__(self, cache_path: str) -> None:
        self.cache_path = cache_path

    def get_path(self, filename: str) -> str:
        return os.path.join(self.cache_path, filename)

    def is_cached(self, filename: str) -> bool:
        return os.path.exists(self.get_path(filename))

    def all_cached(self) -> bool:
        return all(self.is_cached(f) for f in CDN_ASSETS)

    def ensure_cached(self, quiet: bool = False) -> None:
        """Download any missing CDN assets to cache_path."""
        if self.all_cached():
            return
        os.makedirs(self.cache_path, exist_ok=True)
        for filename, url in CDN_ASSETS.items():
            if self.is_cached(filename):
                continue
            if not quiet:
                print(' * Downloading', filename, file=sys.stderr)
            try:
                urllib.request.urlretrieve(url, self.get_path(filename))
            except Exception as ex:
                if not quiet:
                    print(' * Warning: failed to download', filename,
                          '-', ex, file=sys.stderr)

    def clear(self) -> None:
        """Remove the cache directory."""
        if self.cache_path and os.path.exists(self.cache_path):
            shutil.rmtree(self.cache_path)
