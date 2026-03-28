import errno
import io
import mimetypes
import os
import posixpath
import sys
from abc import ABCMeta, abstractmethod
from pathlib import Path

from .config import DEFAULT_FILENAMES, DEFAULT_FILENAME, SUPPORTED_EXTENSIONS
from .exceptions import ReadmeNotFoundError


def _safe_join(directory: str, *pathnames: str, follow_symlinks: bool = False) -> str:
    """Join paths safely, raising ReadmeNotFoundError on traversal.

    Uses Path.relative_to() which is immune to prefix collisions
    (e.g. /home/user vs /home/user.hidden) unlike string startswith.

    If follow_symlinks is False (default), rejects paths that contain
    symlinks pointing outside the base directory.
    """
    base = Path(directory).resolve()
    target = (base / os.path.join(*pathnames)).resolve()
    try:
        target.relative_to(base)
    except ValueError:
        raise ReadmeNotFoundError(str(target))
    if not follow_symlinks:
        # Walk each component to check for symlinks escaping root
        check = base
        for part in Path(os.path.join(*pathnames)).parts:
            check = check / part
            if check.is_symlink():
                real = check.resolve()
                try:
                    real.relative_to(base)
                except ValueError:
                    raise ReadmeNotFoundError(str(check))
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

    def is_directory(self, subpath: str | None = None) -> bool:
        return False

    def last_updated(self, subpath: str | None = None) -> float | None:
        return None

    def list_directory(self, subpath: str | None = None) -> list[dict[str, str]]:
        return []

    @abstractmethod
    def read(self, subpath: str | None = None) -> str | bytes:
        pass


class DirectoryReader(ReadmeReader):
    """
    Reads Readme files from URL subpaths. Supports directory browsing
    when a directory has no README file.
    """

    def __init__(self, path: str | None = None, silent: bool = False) -> None:
        super().__init__()
        if path is None:
            path = "."
        path = os.path.normpath(path)

        if os.path.isdir(path):
            self.root_directory = os.path.abspath(path)
            readme = self._find_readme(self.root_directory)
            self.root_filename = readme  # None if no README found
        elif os.path.exists(path) or silent:
            abspath = os.path.abspath(path)
            self.root_filename = abspath
            self.root_directory = os.path.dirname(abspath)
        else:
            raise ReadmeNotFoundError(path, "File not found: " + path)

    def _find_readme(self, dirpath: str) -> str | None:
        """Find a README file in a directory. Returns None if not found."""
        for filename in DEFAULT_FILENAMES:
            full_path = os.path.join(dirpath, filename)
            if os.path.exists(full_path):
                return full_path
        return None

    def _read_text(self, filename: str) -> str:
        with io.open(filename, "rt", encoding="utf-8") as f:
            return f.read()

    def _read_binary(self, filename: str) -> bytes:
        with io.open(filename, "rb") as f:
            return f.read()

    def normalize_subpath(self, subpath: str | None) -> str | None:
        if subpath is None:
            return None
        subpath = posixpath.normpath(subpath)
        filename = os.path.normpath(_safe_join(self.root_directory, subpath))
        if os.path.isdir(filename):
            subpath += "/"
        return subpath

    def readme_for(self, subpath: str | None) -> str | None:
        """Return the file to read for the given subpath, or None for
        a directory with no README."""
        if subpath is None:
            return self.root_filename  # may be None
        filename = os.path.normpath(_safe_join(self.root_directory, subpath))
        if not os.path.exists(filename):
            raise ReadmeNotFoundError(filename)
        if os.path.isdir(filename):
            return self._find_readme(filename)
        return filename

    def filename_for(self, subpath: str | None) -> str | None:
        try:
            filename = self.readme_for(subpath)
            if filename is None:
                return None
            return os.path.relpath(filename, self.root_directory)
        except ReadmeNotFoundError:
            return None

    def is_binary(self, subpath: str | None = None) -> bool:
        mimetype = self.mimetype_for(subpath)
        return bool(mimetype and not mimetype.startswith("text/"))

    def is_directory(self, subpath: str | None = None) -> bool:
        if subpath is None:
            return os.path.isdir(self.root_directory)
        try:
            filename = os.path.normpath(_safe_join(self.root_directory, subpath))
            return os.path.isdir(filename)
        except ReadmeNotFoundError:
            return False

    def last_updated(self, subpath: str | None = None) -> float | None:
        try:
            readme = self.readme_for(subpath)
            if readme is None:
                return None
            return os.path.getmtime(readme)
        except ReadmeNotFoundError:
            return None
        except OSError as ex:
            if ex.errno == errno.ENOENT:
                return None
            raise

    def list_directory(self, subpath: str | None = None) -> list[dict[str, str]]:
        """List .md files and subdirectories at subpath."""
        if subpath is None:
            dirpath = self.root_directory
        else:
            dirpath = _safe_join(self.root_directory, subpath)
        if not os.path.isdir(dirpath):
            return []
        entries: list[dict[str, str]] = []
        for name in sorted(os.listdir(dirpath)):
            if name.startswith("."):
                continue
            full = os.path.join(dirpath, name)
            if os.path.isdir(full):
                entries.append({"name": name, "type": "directory"})
            elif any(name.endswith(ext) for ext in SUPPORTED_EXTENSIONS):
                entries.append({"name": name, "type": "file"})
        return entries

    def read(self, subpath: str | None = None) -> str | bytes:
        is_binary = self.is_binary(subpath)
        readme = self.readme_for(subpath)
        if readme is None:
            raise ReadmeNotFoundError(subpath or self.root_directory, "No README found")
        try:
            if is_binary:
                return self._read_binary(readme)
            return self._read_text(readme)
        except OSError as ex:
            if ex.errno == errno.ENOENT:
                raise ReadmeNotFoundError(readme)
            raise


class TextReader(ReadmeReader):
    """
    Reads Readme content from the provided string.
    """

    def __init__(self, text: str, display_filename: str | None = None) -> None:
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
        super().__init__("", display_filename)

    def read(self, subpath: str | None = None) -> str:
        if not self.text and subpath is None:
            self.text = self.read_stdin()
        return super().read(subpath)

    def read_stdin(self) -> str:
        return sys.stdin.read()
