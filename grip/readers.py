import errno
import io
import mimetypes
import os
import posixpath
import sys
from abc import ABCMeta, abstractmethod
from pathlib import Path

from .config import DEFAULT_FILENAMES, DEFAULT_FILENAME
from .exceptions import ReadmeNotFoundError


def _safe_join(directory: str, *pathnames: str) -> str:
    """Join paths safely, raising ReadmeNotFoundError on traversal."""
    base = Path(directory).resolve()
    target = (base / os.path.join(*pathnames)).resolve()
    if target != base and not str(target).startswith(str(base) + os.sep):
        raise ReadmeNotFoundError(str(target))
    return str(target)


class ReadmeReader(object, metaclass=ABCMeta):
    """
    Reads Readme content from a URL subpath.
    """
    def __init__(self) -> None:
        super().__init__()

    def normalize_subpath(self, subpath: str | None) -> str | None:
        if subpath is None:
            return None
        return posixpath.normpath(subpath)

    def filename_for(self, subpath: str | None) -> str | None:
        return None

    def mimetype_for(self, subpath: str | None = None) -> str | None:
        if subpath is None:
            subpath = DEFAULT_FILENAME
        mimetype, _ = mimetypes.guess_type(subpath)
        return mimetype

    def is_binary(self, subpath: str | None = None) -> bool:
        return False

    def last_updated(self, subpath: str | None = None) -> float | None:
        return None

    @abstractmethod
    def read(self, subpath: str | None = None) -> str | bytes:
        pass


class DirectoryReader(ReadmeReader):
    """
    Reads Readme files from URL subpaths.
    """
    def __init__(self, path: str | None = None,
                 silent: bool = False) -> None:
        super().__init__()
        root_filename = os.path.abspath(self._resolve_readme(path, silent))
        self.root_filename = root_filename
        self.root_directory = os.path.dirname(root_filename)

    def _find_file(self, path: str, silent: bool = False) -> str:
        for filename in DEFAULT_FILENAMES:
            full_path = os.path.join(path, filename) if path else filename
            if os.path.exists(full_path):
                return full_path
        if silent:
            return os.path.join(path, DEFAULT_FILENAME)
        raise ReadmeNotFoundError(path)

    def _resolve_readme(self, path: str | None = None,
                        silent: bool = False) -> str:
        if path is None:
            path = '.'
        path = os.path.normpath(path)
        if os.path.isdir(path):
            return self._find_file(path, silent)
        if silent or os.path.exists(path):
            return path
        raise ReadmeNotFoundError(path, 'File not found: ' + path)

    def _read_text(self, filename: str) -> str:
        with io.open(filename, 'rt', encoding='utf-8') as f:
            return f.read()

    def _read_binary(self, filename: str) -> bytes:
        with io.open(filename, 'rb') as f:
            return f.read()

    def normalize_subpath(self, subpath: str | None) -> str | None:
        if subpath is None:
            return None
        subpath = posixpath.normpath(subpath)
        filename = os.path.normpath(_safe_join(self.root_directory, subpath))
        if os.path.isdir(filename):
            subpath += '/'
        return subpath

    def readme_for(self, subpath: str | None) -> str:
        if subpath is None:
            return self.root_filename
        filename = os.path.normpath(_safe_join(self.root_directory, subpath))
        if not os.path.exists(filename):
            raise ReadmeNotFoundError(filename)
        if os.path.isdir(filename):
            return self._find_file(filename)
        return filename

    def filename_for(self, subpath: str | None) -> str | None:
        try:
            filename = self.readme_for(subpath)
            return os.path.relpath(filename, self.root_directory)
        except ReadmeNotFoundError:
            return None

    def is_binary(self, subpath: str | None = None) -> bool:
        mimetype = self.mimetype_for(subpath)
        return bool(mimetype and not mimetype.startswith('text/'))

    def last_updated(self, subpath: str | None = None) -> float | None:
        try:
            return os.path.getmtime(self.readme_for(subpath))
        except ReadmeNotFoundError:
            return None
        except OSError as ex:
            if ex.errno == errno.ENOENT:
                return None
            raise

    def read(self, subpath: str | None = None) -> str | bytes:
        is_binary = self.is_binary(subpath)
        filename = self.readme_for(subpath)
        try:
            if is_binary:
                return self._read_binary(filename)
            return self._read_text(filename)
        except OSError as ex:
            if ex.errno == errno.ENOENT:
                raise ReadmeNotFoundError(filename)
            raise


class TextReader(ReadmeReader):
    """
    Reads Readme content from the provided string.
    """
    def __init__(self, text: str,
                 display_filename: str | None = None) -> None:
        super().__init__()
        self.text = text
        self.display_filename = display_filename

    def filename_for(self, subpath: str | None) -> str | None:
        if subpath is not None:
            return None
        return self.display_filename

    def read(self, subpath: str | None = None) -> str:
        if subpath is not None:
            raise ReadmeNotFoundError(subpath)
        return self.text


class StdinReader(TextReader):
    """
    Reads Readme text from STDIN.
    """
    def __init__(self, display_filename: str | None = None) -> None:
        super().__init__('', display_filename)

    def read(self, subpath: str | None = None) -> str:
        if not self.text and subpath is None:
            self.text = self.read_stdin()
        return super().read(subpath)

    def read_stdin(self) -> str:
        return sys.stdin.read()
