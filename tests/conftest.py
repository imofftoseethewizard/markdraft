import os
import sys


DIRNAME = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(1, os.path.dirname(DIRNAME))


import pytest  # noqa: E402

from grip import DirectoryReader, Grip, GripperRenderer, TextReader  # noqa: E402
from mocks import GitHubAssetManagerMock  # noqa: E402


@pytest.fixture
def grip_app(tmp_path, monkeypatch):
    """Factory fixture: returns a function that creates a Grip test client."""
    def _make(text, **kwargs):
        monkeypatch.setenv('GRIPHOME', str(tmp_path))
        filename = kwargs.pop('display_filename', 'README.md')
        source = TextReader(text, filename)
        assets = GitHubAssetManagerMock()
        app = Grip(source, assets=assets, **kwargs)
        return app.test_client()
    return _make


@pytest.fixture
def grip_dir_app(tmp_path, monkeypatch):
    """Factory fixture: creates a Grip app serving a temp directory."""
    def _make(files, **kwargs):
        monkeypatch.setenv('GRIPHOME', str(tmp_path / '.grip'))
        content_dir = tmp_path / 'content'
        content_dir.mkdir(exist_ok=True)
        for name, content in files.items():
            path = content_dir / name
            path.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(content, bytes):
                path.write_bytes(content)
            else:
                path.write_text(content)
        source = DirectoryReader(str(content_dir))
        assets = GitHubAssetManagerMock()
        app = Grip(source, assets=assets, **kwargs)
        return app.test_client()
    return _make
