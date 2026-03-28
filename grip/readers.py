import errno
import io
import mimetypes
import os
import sys
from abc import ABCMeta, abstractmethod
from pathlib import Path

from .config import DEFAULT_FILENAMES, DEFAULT_FILENAME
from .exceptions import ReadmeNotFoundError


def _safe_join(directory, *pathnames):
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
    def __init__(self):
        super(ReadmeReader, self).__init__()

    def normalize_subpath(self, subpath):
        if subpath is None:
            return None
        import posixpath
        return posixpath.normpath(subpath)

    def filename_for(self, subpath):
        return None

    def mimetype_for(self, subpath=None):
        if subpath is None:
            subpath = DEFAULT_FILENAME
        mimetype, _ = mimetypes.guess_type(subpath)
        return mimetype

    def is_binary(self, subpath=None):
        return False

    def last_updated(self, subpath=None):
        return None

    @abstractmethod
    def read(self, subpath=None):
        pass


class DirectoryReader(ReadmeReader):
    """
    Reads Readme files from URL subpaths.
    """
    def __init__(self, path=None, silent=False):
        super(DirectoryReader, self).__init__()
        root_filename = os.path.abspath(self._resolve_readme(path, silent))
        self.root_filename = root_filename
        self.root_directory = os.path.dirname(root_filename)

    def _find_file(self, path, silent=False):
        for filename in DEFAULT_FILENAMES:
            full_path = os.path.join(path, filename) if path else filename
            if os.path.exists(full_path):
                return full_path
        if silent:
            return os.path.join(path, DEFAULT_FILENAME)
        raise ReadmeNotFoundError(path)

    def _resolve_readme(self, path=None, silent=False):
        if path is None:
            path = '.'
        path = os.path.normpath(path)
        if os.path.isdir(path):
            return self._find_file(path, silent)
        if silent or os.path.exists(path):
            return path
        raise ReadmeNotFoundError(path, 'File not found: ' + path)

    def _read_text(self, filename):
        with io.open(filename, 'rt', encoding='utf-8') as f:
            return f.read()

    def _read_binary(self, filename):
        with io.open(filename, 'rb') as f:
            return f.read()

    def normalize_subpath(self, subpath):
        import posixpath
        if subpath is None:
            return None
        subpath = posixpath.normpath(subpath)
        filename = os.path.normpath(_safe_join(self.root_directory, subpath))
        if os.path.isdir(filename):
            subpath += '/'
        return subpath

    def readme_for(self, subpath):
        if subpath is None:
            return self.root_filename
        filename = os.path.normpath(_safe_join(self.root_directory, subpath))
        if not os.path.exists(filename):
            raise ReadmeNotFoundError(filename)
        if os.path.isdir(filename):
            return self._find_file(filename)
        return filename

    def filename_for(self, subpath):
        try:
            filename = self.readme_for(subpath)
            return os.path.relpath(filename, self.root_directory)
        except ReadmeNotFoundError:
            return None

    def is_binary(self, subpath=None):
        mimetype = self.mimetype_for(subpath)
        return mimetype and not mimetype.startswith('text/')

    def last_updated(self, subpath=None):
        try:
            return os.path.getmtime(self.readme_for(subpath))
        except ReadmeNotFoundError:
            return None
        except (OSError, EnvironmentError) as ex:
            if ex.errno == errno.ENOENT:
                return None
            raise

    def read(self, subpath=None):
        is_binary = self.is_binary(subpath)
        filename = self.readme_for(subpath)
        try:
            if is_binary:
                return self._read_binary(filename)
            return self._read_text(filename)
        except (OSError, EnvironmentError) as ex:
            if ex.errno == errno.ENOENT:
                raise ReadmeNotFoundError(filename)
            raise


class TextReader(ReadmeReader):
    """
    Reads Readme content from the provided string.
    """
    def __init__(self, text, display_filename=None):
        super(TextReader, self).__init__()
        self.text = text
        self.display_filename = display_filename

    def filename_for(self, subpath):
        if subpath is not None:
            return None
        return self.display_filename

    def read(self, subpath=None):
        if subpath is not None:
            raise ReadmeNotFoundError(subpath)
        return self.text


class StdinReader(TextReader):
    """
    Reads Readme text from STDIN.
    """
    def __init__(self, display_filename=None):
        super(StdinReader, self).__init__(None, display_filename)

    def read(self, subpath=None):
        if self.text is None and subpath is None:
            self.text = self.read_stdin()
        return super(StdinReader, self).read(subpath)

    def read_stdin(self):
        return sys.stdin.read()
