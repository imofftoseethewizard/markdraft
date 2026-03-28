"""
Unit tests for readers, asset cache, file watcher, browser helpers,
config loading, address parsing, and exceptions.
"""

import os
import socket
import threading
import time
from unittest import mock

import pytest

from markdraft.assets import AssetCache
from markdraft.browser import (
    is_server_running,
    start_browser,
    start_browser_when_ready,
    wait_for_server,
)
from markdraft.command import _resolve_path_address, _split_address
from markdraft.config import CDN_ASSETS, load_user_settings
from markdraft.exceptions import ReadmeNotFoundError
from markdraft.readers import DirectoryReader, StdinReader, TextReader
from markdraft.watcher import FileWatcher


DIRNAME = os.path.dirname(os.path.abspath(__file__))


def input_path(*parts: str) -> str:
    return os.path.join(DIRNAME, "input", *parts)


# ---------------------------------------------------------------------------
# Readers
# ---------------------------------------------------------------------------


class TestDirectoryReader:
    def test_finds_readme_in_directory(self):
        reader = DirectoryReader(input_path("default"))
        assert reader.root_filename.endswith("README.md")

    def test_accepts_explicit_file(self):
        reader = DirectoryReader(input_path("gfm-test.md"))
        assert reader.root_filename.endswith("gfm-test.md")

    def test_silent_missing(self):
        reader = DirectoryReader(input_path("empty"), silent=True)
        assert reader.root_filename.endswith("README.md")

    def test_raises_missing(self):
        with pytest.raises(ReadmeNotFoundError):
            DirectoryReader(input_path("empty"))

    def test_normalize_none(self):
        reader = DirectoryReader(input_path("default"))
        assert reader.normalize_subpath(None) is None

    def test_normalize_directory_adds_slash(self, tmp_path):
        (tmp_path / "README.md").write_text("hi")
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "README.md").write_text("sub")
        reader = DirectoryReader(str(tmp_path))
        assert reader.normalize_subpath("sub") == "sub/"

    def test_normalize_file_no_slash(self, tmp_path):
        (tmp_path / "README.md").write_text("hi")
        (tmp_path / "other.md").write_text("other")
        reader = DirectoryReader(str(tmp_path))
        assert reader.normalize_subpath("other.md") == "other.md"

    def test_traversal_blocked(self, tmp_path):
        (tmp_path / "README.md").write_text("hi")
        reader = DirectoryReader(str(tmp_path))
        with pytest.raises(ReadmeNotFoundError):
            reader.normalize_subpath("../escape")

    def test_is_binary_png(self):
        reader = DirectoryReader(DIRNAME, silent=True)
        assert reader.is_binary("input/img.png")

    def test_is_binary_markdown(self):
        reader = DirectoryReader(DIRNAME, silent=True)
        assert not reader.is_binary("input/gfm-test.md")

    def test_last_updated_existing(self):
        reader = DirectoryReader(input_path("default"))
        mtime = reader.last_updated()
        assert isinstance(mtime, float)
        assert mtime > 0

    def test_last_updated_missing(self):
        reader = DirectoryReader(DIRNAME, silent=True)
        assert reader.last_updated("nonexistent") is None

    def test_read_text(self):
        reader = DirectoryReader(input_path("default"))
        content = reader.read()
        assert isinstance(content, str)
        assert "README" in content

    def test_read_binary(self):
        reader = DirectoryReader(DIRNAME, silent=True)
        content = reader.read("input/img.png")
        assert isinstance(content, bytes)
        assert content[:4] == b"\x89PNG"

    def test_read_missing_raises(self):
        reader = DirectoryReader(DIRNAME, silent=True)
        with pytest.raises(ReadmeNotFoundError):
            reader.read("nonexistent.md")

    def test_filename_for_root(self):
        reader = DirectoryReader(input_path("default"))
        assert reader.filename_for(None) == "README.md"

    def test_filename_for_missing(self):
        reader = DirectoryReader(DIRNAME, silent=True)
        assert reader.filename_for("nonexistent") is None


class TestTextReader:
    def test_read(self):
        assert TextReader("hello").read() == "hello"

    def test_read_subpath_raises(self):
        with pytest.raises(ReadmeNotFoundError):
            TextReader("hello").read("sub")

    def test_filename_for_none(self):
        assert TextReader("hi", "f.md").filename_for(None) == "f.md"

    def test_filename_for_subpath(self):
        assert TextReader("hi", "f.md").filename_for("x") is None

    def test_normalize_subpath(self):
        assert TextReader("hi").normalize_subpath(None) is None
        assert TextReader("hi").normalize_subpath("x/y") == "x/y"


class TestStdinReader:
    def test_reads_once(self):
        class MockStdin(StdinReader):
            def __init__(self):
                super().__init__()
                self.call_count = 0

            def read_stdin(self):
                self.call_count += 1
                return "stdin text"

        reader = MockStdin()
        assert reader.read() == "stdin text"
        assert reader.read() == "stdin text"
        assert reader.call_count == 1

    def test_subpath_raises(self):
        class MockStdin(StdinReader):
            def read_stdin(self):
                return "text"

        with pytest.raises(ReadmeNotFoundError):
            MockStdin().read("sub")


# ---------------------------------------------------------------------------
# Asset cache
# ---------------------------------------------------------------------------


class TestAssetCache:
    def test_get_path(self, tmp_path):
        cache = AssetCache(str(tmp_path))
        assert cache.get_path("x.js") == os.path.join(str(tmp_path), "x.js")

    def test_is_cached_true(self, tmp_path):
        (tmp_path / "x.js").write_text("content")
        assert AssetCache(str(tmp_path)).is_cached("x.js")

    def test_is_cached_false(self, tmp_path):
        assert not AssetCache(str(tmp_path)).is_cached("x.js")

    def test_all_cached_true(self, tmp_path):
        for name in CDN_ASSETS:
            (tmp_path / name).write_text("x")
        assert AssetCache(str(tmp_path)).all_cached()

    def test_all_cached_false(self, tmp_path):
        assert not AssetCache(str(tmp_path)).all_cached()

    def test_ensure_downloads(self, tmp_path):
        cache = AssetCache(str(tmp_path / "cache"))
        with mock.patch("markdraft.assets.urllib.request.urlretrieve") as m:
            cache.ensure_cached(quiet=True)
            assert m.call_count == len(CDN_ASSETS)

    def test_ensure_skips_existing(self, tmp_path):
        for name in CDN_ASSETS:
            (tmp_path / name).write_text("x")
        with mock.patch("markdraft.assets.urllib.request.urlretrieve") as m:
            AssetCache(str(tmp_path)).ensure_cached(quiet=True)
            assert m.call_count == 0

    def test_ensure_handles_failure(self, tmp_path, capsys):
        cache = AssetCache(str(tmp_path / "cache"))
        with mock.patch(
            "markdraft.assets.urllib.request.urlretrieve",
            side_effect=Exception("network error"),
        ):
            cache.ensure_cached(quiet=False)
        assert "Warning" in capsys.readouterr().err

    def test_clear_removes_dir(self, tmp_path):
        d = tmp_path / "cache"
        d.mkdir()
        (d / "test.css").write_text("body{}")
        AssetCache(str(d)).clear()
        assert not d.exists()

    def test_clear_missing_dir(self, tmp_path):
        AssetCache(str(tmp_path / "nope")).clear()  # no error


# ---------------------------------------------------------------------------
# File watcher
# ---------------------------------------------------------------------------


class TestFileWatcher:
    def test_yields_on_change(self, tmp_path):
        md = tmp_path / "README.md"
        md.write_text("v1")
        reader = DirectoryReader(str(tmp_path))
        watcher = FileWatcher(reader, interval=0.05)
        shutdown = threading.Event()

        results = []

        def watch_thread():
            for changed in watcher.watch(shutdown):
                results.append(changed)
                shutdown.set()

        t = threading.Thread(target=watch_thread, daemon=True)
        t.start()
        time.sleep(0.1)
        md.write_text("v2")
        t.join(timeout=2)
        assert results == [True]

    def test_exits_on_shutdown(self, tmp_path):
        md = tmp_path / "README.md"
        md.write_text("v1")
        reader = DirectoryReader(str(tmp_path))
        watcher = FileWatcher(reader, interval=0.05)
        shutdown = threading.Event()

        results = []

        def watch_thread():
            for changed in watcher.watch(shutdown):
                results.append(changed)

        t = threading.Thread(target=watch_thread, daemon=True)
        t.start()
        time.sleep(0.1)
        shutdown.set()
        t.join(timeout=2)
        assert results == []

    def test_no_yield_without_change(self, tmp_path):
        md = tmp_path / "README.md"
        md.write_text("v1")
        reader = DirectoryReader(str(tmp_path))
        watcher = FileWatcher(reader, interval=0.05)
        shutdown = threading.Event()

        results = []

        def watch_thread():
            for changed in watcher.watch(shutdown):
                results.append(changed)

        t = threading.Thread(target=watch_thread, daemon=True)
        t.start()
        time.sleep(0.2)
        shutdown.set()
        t.join(timeout=2)
        assert results == []


# ---------------------------------------------------------------------------
# Browser helpers
# ---------------------------------------------------------------------------


class TestBrowser:
    def test_is_server_running_true(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        _, port = sock.getsockname()
        try:
            assert is_server_running("127.0.0.1", port)
        finally:
            sock.close()

    def test_is_server_running_false(self):
        assert not is_server_running("127.0.0.1", 1)

    def test_wait_for_server_cancel(self):
        cancel = threading.Event()
        cancel.set()
        assert wait_for_server("127.0.0.1", 1, cancel) is False

    def test_start_browser_when_ready(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        _, port = sock.getsockname()
        cancel = threading.Event()
        try:
            with mock.patch("markdraft.browser.webbrowser.open") as m:
                t = start_browser_when_ready("127.0.0.1", port, cancel)
                t.join(timeout=3)
                m.assert_called_once()
                assert str(port) in m.call_args[0][0]
        finally:
            cancel.set()
            sock.close()

    def test_start_browser_exception_swallowed(self):
        with mock.patch(
            "markdraft.browser.webbrowser.open", side_effect=Exception("no browser")
        ):
            start_browser("http://localhost:1234/")  # no crash


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------


class TestConfigLoading:
    def test_load_missing_file(self, tmp_path):
        result = load_user_settings(str(tmp_path / "nonexistent"))
        assert result == {}

    def test_load_settings(self, tmp_path):
        settings = tmp_path / "settings.py"
        settings.write_text('HOST = "0.0.0.0"\nPORT = 9000\n')
        result = load_user_settings(str(tmp_path))
        assert result["HOST"] == "0.0.0.0"
        assert result["PORT"] == 9000

    def test_load_ignores_lowercase(self, tmp_path):
        settings = tmp_path / "settings.py"
        settings.write_text('HOST = "0.0.0.0"\nfoo = "bar"\n')
        result = load_user_settings(str(tmp_path))
        assert "HOST" in result
        assert "foo" not in result

    def test_env_var_override(self, tmp_path, monkeypatch):
        settings = tmp_path / "settings.py"
        settings.write_text("QUIET = True\n")
        monkeypatch.setenv("MARKDRAFT_HOME", str(tmp_path))
        result = load_user_settings()
        assert result["QUIET"] is True


class TestResolveConfig:
    def test_defaults(self):
        from markdraft.api import _resolve_config

        cfg = _resolve_config()
        assert cfg["host"] == "localhost"
        assert cfg["port"] == 6419
        assert cfg["autorefresh"] is True
        assert cfg["quiet"] is False

    def test_cli_overrides(self):
        from markdraft.api import _resolve_config

        cfg = _resolve_config(host="0.0.0.0", port=8080, quiet=True)
        assert cfg["host"] == "0.0.0.0"
        assert cfg["port"] == 8080
        assert cfg["quiet"] is True

    def test_settings_file_override(self, tmp_path, monkeypatch):
        from markdraft.api import _resolve_config

        settings = tmp_path / "settings.py"
        settings.write_text("PORT = 9000\n")
        monkeypatch.setenv("MARKDRAFT_HOME", str(tmp_path))
        cfg = _resolve_config()
        assert cfg["port"] == 9000


# ---------------------------------------------------------------------------
# Address parsing
# ---------------------------------------------------------------------------


class TestSplitAddress:
    def test_none(self):
        assert _split_address(None) == (None, None)

    def test_empty(self):
        assert _split_address("") == (None, None)

    def test_port_only(self):
        assert _split_address("8080") == (None, 8080)

    def test_host_only(self):
        assert _split_address("localhost") == ("localhost", None)

    def test_host_port(self):
        assert _split_address("localhost:8080") == ("localhost", 8080)

    def test_host_bad_port(self):
        assert _split_address("host:abc") == ("host:abc", None)

    def test_colon_port(self):
        assert _split_address(":8080") == (None, 8080)


class TestResolvePathAddress:
    def test_none_none(self):
        assert _resolve_path_address(None, None) == (None, None)

    def test_path_only(self):
        assert _resolve_path_address("README.md", None) == ("README.md", None)

    def test_port_as_path(self):
        assert _resolve_path_address("8080", None) == (None, "8080")

    def test_both(self):
        assert _resolve_path_address("README.md", "8080") == ("README.md", "8080")

    def test_stdin(self):
        assert _resolve_path_address("-", None) == ("-", None)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class TestExceptions:
    def test_str_default(self):
        assert str(ReadmeNotFoundError()) == "README not found"

    def test_str_with_path(self):
        assert str(ReadmeNotFoundError(".")) == "No README found at ."

    def test_str_with_message(self):
        assert str(ReadmeNotFoundError("p", "custom msg")) == "custom msg"

    def test_filename_attribute(self):
        err = ReadmeNotFoundError("file.md")
        assert err.filename == "file.md"

    def test_repr(self):
        r = repr(ReadmeNotFoundError("p", "m"))
        assert "ReadmeNotFoundError" in r

    def test_is_file_not_found(self):
        assert isinstance(ReadmeNotFoundError(), FileNotFoundError)
