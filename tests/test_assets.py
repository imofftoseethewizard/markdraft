"""
Tests for the asset cache.
"""

import os
from unittest import mock

from markdraft.assets import AssetCache
from markdraft.config import CDN_ASSETS


class TestAssetCache:

    def test_get_path(self, tmp_path):
        cache = AssetCache(str(tmp_path))
        assert cache.get_path("test.js") == os.path.join(str(tmp_path), "test.js")

    def test_is_cached_false(self, tmp_path):
        cache = AssetCache(str(tmp_path))
        assert not cache.is_cached("test.js")

    def test_is_cached_true(self, tmp_path):
        (tmp_path / "test.js").write_text("content")
        cache = AssetCache(str(tmp_path))
        assert cache.is_cached("test.js")

    def test_all_cached_false(self, tmp_path):
        cache = AssetCache(str(tmp_path))
        assert not cache.all_cached()

    def test_all_cached_true(self, tmp_path):
        for filename in CDN_ASSETS:
            (tmp_path / filename).write_text("content")
        cache = AssetCache(str(tmp_path))
        assert cache.all_cached()

    def test_ensure_cached_downloads(self, tmp_path):
        cache_path = str(tmp_path / "cache")
        cache = AssetCache(cache_path)

        with mock.patch("markdraft.assets.urllib.request.urlretrieve") as m:
            cache.ensure_cached(quiet=True)
            assert m.call_count == len(CDN_ASSETS)

    def test_ensure_cached_skips_existing(self, tmp_path):
        for filename in CDN_ASSETS:
            (tmp_path / filename).write_text("content")
        cache = AssetCache(str(tmp_path))

        with mock.patch("markdraft.assets.urllib.request.urlretrieve") as m:
            cache.ensure_cached(quiet=True)
            assert m.call_count == 0

    def test_clear_removes_directory(self, tmp_path):
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        (cache_dir / "test.css").write_text("body {}")
        cache = AssetCache(str(cache_dir))
        cache.clear()
        assert not cache_dir.exists()

    def test_clear_nonexistent_directory(self, tmp_path):
        cache = AssetCache(str(tmp_path / "nonexistent"))
        cache.clear()  # should not raise
