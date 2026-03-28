import os
import sys
import threading
import time
import urllib.request

DIRNAME = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(1, os.path.dirname(DIRNAME))

import pytest  # noqa: E402

from grip.assets import AssetCache  # noqa: E402
from grip.readers import DirectoryReader, TextReader  # noqa: E402
from grip.server import GripServer  # noqa: E402


class TestClient:
    """Simple HTTP test client for GripServer."""

    def __init__(self, host, port):
        self.base_url = 'http://{0}:{1}'.format(host, port)

    def get(self, path, follow_redirects=False):
        url = self.base_url + path
        req = urllib.request.Request(url)
        try:
            resp = urllib.request.urlopen(req, timeout=5)
            return _Response(resp.status, resp.read(),
                             dict(resp.headers), resp.url)
        except urllib.error.HTTPError as e:
            return _Response(e.code, e.read(),
                             dict(e.headers), url)


class _Response:
    def __init__(self, status_code, data, headers, url):
        self.status_code = status_code
        self.data = data
        self.headers = headers
        self.url = url

    def text(self):
        return self.data.decode('utf-8', errors='replace')

    def json(self):
        import json
        return json.loads(self.data)


class MockAssetCache(AssetCache):
    """Asset cache that doesn't download anything."""
    def ensure_cached(self, quiet=False):
        os.makedirs(self.cache_path, exist_ok=True)


@pytest.fixture
def grip_server(tmp_path):
    """Factory fixture that starts a GripServer on a random port."""
    servers = []

    def _make(reader, **config_overrides):
        cache_path = str(tmp_path / 'cache')
        assets = MockAssetCache(cache_path)
        config = dict(
            autorefresh=True,
            quiet=True,
            theme='light',
            title=None,
            user_content=False,
            wide=False,
            grip_url='/__',
        )
        config.update(config_overrides)
        server = GripServer(('127.0.0.1', 0), reader, assets, config)
        host, port = server.server_address
        thread = threading.Thread(target=server.serve_forever)
        thread.daemon = True
        thread.start()
        servers.append(server)
        return TestClient(host, port)

    yield _make

    for s in servers:
        s.shutdown_event.set()
        s.shutdown()


@pytest.fixture
def grip_text_server(tmp_path, grip_server):
    """Factory: create a server serving in-memory text."""
    def _make(text, **kwargs):
        filename = kwargs.pop('display_filename', 'README.md')
        reader = TextReader(text, filename)
        return grip_server(reader, **kwargs)
    return _make


@pytest.fixture
def grip_dir_server(tmp_path, grip_server):
    """Factory: create a server serving a temp directory."""
    def _make(files, **kwargs):
        content_dir = tmp_path / 'content'
        content_dir.mkdir(exist_ok=True)
        for name, content in files.items():
            path = content_dir / name
            path.parent.mkdir(parents=True, exist_ok=True)
            if isinstance(content, bytes):
                path.write_bytes(content)
            else:
                path.write_text(content)
        reader = DirectoryReader(str(content_dir))
        return grip_server(reader, **kwargs)
    return _make
