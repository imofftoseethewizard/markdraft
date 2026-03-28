"""
Tests for Markdraft's public API and core components.
"""

import os
import posixpath

import pytest

from markdraft import (
    DEFAULT_FILENAME,
    DirectoryReader,
    ReadmeNotFoundError,
    StdinReader,
    TextReader,
    clear_cache,
    export,
)
from markdraft.assets import AssetCache

DIRNAME = os.path.dirname(os.path.abspath(__file__))


def input_filename(*parts):
    return os.path.join(DIRNAME, "input", *parts)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


def test_exceptions():
    assert str(ReadmeNotFoundError()) == "README not found"
    assert str(ReadmeNotFoundError(".")) == "No README found at ."
    assert str(ReadmeNotFoundError("some/path", "Overridden")) == "Overridden"
    assert ReadmeNotFoundError().filename is None
    assert ReadmeNotFoundError(DEFAULT_FILENAME).filename == DEFAULT_FILENAME


# ---------------------------------------------------------------------------
# Readers
# ---------------------------------------------------------------------------


def test_directory_reader():
    input_path = "input"
    markdown_path = posixpath.join(input_path, "gfm-test.md")
    default_path = posixpath.join(input_path, "default")
    input_img_path = posixpath.join(input_path, "img.png")

    input_dir = os.path.join(DIRNAME, "input")
    markdown_file = os.path.join(input_dir, "gfm-test.md")
    default_dir = os.path.join(input_dir, "default")
    default_file = os.path.join(default_dir, DEFAULT_FILENAME)

    DirectoryReader(input_filename("default"))
    DirectoryReader(input_filename(default_file))
    DirectoryReader(input_filename(default_file), silent=True)
    DirectoryReader(input_filename("empty"), silent=True)
    with pytest.raises(ReadmeNotFoundError):
        DirectoryReader(input_filename("empty"))
    with pytest.raises(ReadmeNotFoundError):
        DirectoryReader(input_filename("empty", DEFAULT_FILENAME))

    reader = DirectoryReader(DIRNAME, silent=True)
    assert reader.root_filename == os.path.join(DIRNAME, DEFAULT_FILENAME)
    assert reader.root_directory == DIRNAME

    assert reader.normalize_subpath(None) is None
    assert reader.normalize_subpath(".") == "./"
    assert reader.normalize_subpath("./././") == "./"
    assert reader.normalize_subpath("non-existent/.././") == "./"
    assert reader.normalize_subpath("non-existent/") == "non-existent"
    assert reader.normalize_subpath("non-existent") == "non-existent"
    with pytest.raises(ReadmeNotFoundError):
        reader.normalize_subpath("../unsafe")
    with pytest.raises(ReadmeNotFoundError):
        reader.normalize_subpath("/unsafe")
    assert reader.normalize_subpath(input_path) == input_path + "/"
    assert reader.normalize_subpath(markdown_path) == markdown_path
    assert reader.normalize_subpath(markdown_path + "/") == markdown_path

    assert reader.readme_for(None) == os.path.join(DIRNAME, DEFAULT_FILENAME)
    with pytest.raises(ReadmeNotFoundError):
        reader.readme_for("non-existent")
    with pytest.raises(ReadmeNotFoundError):
        reader.readme_for(input_path)
    assert reader.readme_for(markdown_path) == os.path.abspath(markdown_file)
    assert reader.readme_for(default_path) == os.path.abspath(default_file)

    assert reader.filename_for(None) == DEFAULT_FILENAME
    assert reader.filename_for(input_path) is None
    assert reader.filename_for(default_path) == os.path.relpath(
        default_file, reader.root_directory
    )

    assert not reader.is_binary()
    assert not reader.is_binary(input_path)
    assert not reader.is_binary(markdown_path)
    assert reader.is_binary(input_img_path)

    assert reader.last_updated() is None
    assert reader.last_updated(input_path) is None
    assert reader.last_updated(markdown_path) is not None
    assert reader.last_updated(default_path) is not None
    assert DirectoryReader(default_dir).last_updated is not None

    with pytest.raises(ReadmeNotFoundError):
        assert reader.read(input_path) is not None
    assert reader.read(markdown_path)
    assert reader.read(default_path)
    with pytest.raises(ReadmeNotFoundError):
        assert reader.read()
    assert DirectoryReader(default_dir).read() is not None


def test_text_reader():
    text = "Test *Text*"
    filename = DEFAULT_FILENAME

    assert TextReader(text).normalize_subpath(None) is None
    assert TextReader(text).normalize_subpath("././.") == "."
    assert TextReader(text).normalize_subpath(filename) == filename

    assert TextReader(text).filename_for(None) is None
    assert TextReader(text, filename).filename_for(None) == filename
    assert TextReader(text, filename).filename_for(".") is None

    assert TextReader(text).last_updated() is None
    assert TextReader(text, filename).last_updated() is None

    assert TextReader(text).read() == text
    assert TextReader(text, filename).read() == text
    with pytest.raises(ReadmeNotFoundError):
        TextReader(text).read(".")


def test_stdin_reader():
    class StdinMock(StdinReader):
        def __init__(self, mock_text, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._mock = mock_text

        def read_stdin(self):
            return self._mock

    text = "Test *STDIN*"
    assert StdinMock(text).read() == text
    with pytest.raises(ReadmeNotFoundError):
        StdinMock(text).read(".")


# ---------------------------------------------------------------------------
# Asset cache
# ---------------------------------------------------------------------------


class TestAssetCache:

    def test_clear_removes_directory(self, tmp_path):
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        (cache_dir / "test.css").write_text("body {}")
        cache = AssetCache(str(cache_dir))
        cache.clear()
        assert not cache_dir.exists()

    def test_clear_nonexistent(self, tmp_path):
        cache = AssetCache(str(tmp_path / "nonexistent"))
        cache.clear()  # no error


# ---------------------------------------------------------------------------
# Export API
# ---------------------------------------------------------------------------


class TestExport:

    def test_export_to_file(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MARKDRAFT_HOME", str(tmp_path / ".markdraft"))
        md = tmp_path / "README.md"
        md.write_text("# Export Test")
        out = str(tmp_path / "out.html")
        export(str(tmp_path), out_filename=out, quiet=True)
        with open(out) as f:
            html = f.read()
        assert "<!DOCTYPE html>" in html
        assert "# Export Test" in html

    def test_export_to_stdout(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setenv("MARKDRAFT_HOME", str(tmp_path / ".markdraft"))
        md = tmp_path / "README.md"
        md.write_text("# Stdout")
        export(str(tmp_path), out_filename="-", quiet=True)
        captured = capsys.readouterr()
        assert "<!DOCTYPE html>" in captured.out


class TestClearCache:

    def test_clear_cache(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MARKDRAFT_HOME", str(tmp_path))
        clear_cache()  # should not raise
