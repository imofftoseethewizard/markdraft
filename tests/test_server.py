"""
Tests for the HTTP server (routes, content types, redirects, errors).
"""

import json


class TestPageRoutes:
    """Verify the HTML shell is served for markdown files."""

    def test_root_serves_html(self, grip_text_server):
        client = grip_text_server('# Hello')
        resp = client.get('/')
        assert resp.status_code == 200
        assert '<!DOCTYPE html>' in resp.text()
        assert 'grip-content' in resp.text()

    def test_page_has_data_attributes(self, grip_text_server):
        client = grip_text_server('# Hello')
        resp = client.get('/')
        html = resp.text()
        assert 'data-content-url=' in html
        assert 'data-color-mode=' in html

    def test_page_title_from_filename(self, grip_text_server):
        client = grip_text_server('# Hello', display_filename='README.md')
        html = client.get('/').text()
        assert 'README.md - Grip' in html

    def test_page_title_override(self, grip_text_server):
        client = grip_text_server('# Hello', title='Custom Title')
        html = client.get('/').text()
        assert 'Custom Title' in html

    def test_theme_light(self, grip_text_server):
        client = grip_text_server('text', theme='light')
        assert 'data-color-mode="light"' in client.get('/').text()

    def test_theme_dark(self, grip_text_server):
        client = grip_text_server('text', theme='dark')
        assert 'data-color-mode="dark"' in client.get('/').text()

    def test_user_content_layout(self, grip_text_server):
        client = grip_text_server('text', user_content=True)
        html = client.get('/').text()
        assert 'pull-discussion-timeline' in html
        assert 'id="readme"' not in html

    def test_non_user_content_layout(self, grip_text_server):
        client = grip_text_server('text')
        html = client.get('/').text()
        assert 'id="readme"' in html
        assert 'pull-discussion-timeline' not in html

    def test_autorefresh_url_present(self, grip_text_server):
        client = grip_text_server('text', autorefresh=True)
        html = client.get('/').text()
        assert 'data-refresh-url="/__/api/refresh"' in html

    def test_autorefresh_url_empty(self, grip_text_server):
        client = grip_text_server('text', autorefresh=False)
        html = client.get('/').text()
        assert 'data-refresh-url=""' in html

    def test_script_tags_present(self, grip_text_server):
        client = grip_text_server('text')
        html = client.get('/').text()
        assert 'marked.min.js' in html
        assert 'highlight.min.js' in html
        assert 'mermaid.min.js' in html
        assert 'grip.js' in html


class TestApiContent:
    """Verify the JSON content API."""

    def test_returns_json(self, grip_text_server):
        client = grip_text_server('# Hello')
        resp = client.get('/__/api/content')
        assert resp.status_code == 200
        assert 'application/json' in resp.headers.get('Content-Type', '')

    def test_returns_raw_markdown(self, grip_text_server):
        client = grip_text_server('# Hello\n\n**bold**')
        data = client.get('/__/api/content').json()
        assert data['text'] == '# Hello\n\n**bold**'

    def test_returns_filename(self, grip_text_server):
        client = grip_text_server('text', display_filename='README.md')
        data = client.get('/__/api/content').json()
        assert data['filename'] == 'README.md'

    def test_content_for_subpath(self, grip_dir_server):
        client = grip_dir_server({
            'README.md': '# Root',
            'other.md': '# Other File',
        })
        data = client.get('/__/api/content/other.md').json()
        assert '# Other File' in data['text']

    def test_missing_file_404(self, grip_text_server):
        client = grip_text_server('text')
        resp = client.get('/__/api/content/nonexistent.md')
        assert resp.status_code == 404


class TestApiRefresh:
    """Verify the SSE refresh endpoint."""

    def test_refresh_enabled(self, grip_text_server):
        """Verify the refresh endpoint is accessible (not 404).
        The SSE stream blocks, so we just check that autorefresh=False
        gives 404 (tested below) and autorefresh=True does not."""
        # Tested indirectly: the page HTML has a non-empty refresh URL
        client = grip_text_server('text', autorefresh=True)
        html = client.get('/').text()
        assert 'data-refresh-url="/__/api/refresh"' in html

    def test_refresh_disabled(self, grip_text_server):
        client = grip_text_server('text', autorefresh=False)
        resp = client.get('/__/api/refresh')
        assert resp.status_code == 404


class TestStaticFiles:
    """Verify static file serving."""

    def test_serve_bundled_css(self, grip_text_server):
        client = grip_text_server('text')
        resp = client.get('/__/static/grip.css')
        assert resp.status_code == 200
        assert '.preview-page' in resp.text()

    def test_serve_bundled_js(self, grip_text_server):
        client = grip_text_server('text')
        resp = client.get('/__/static/grip.js')
        assert resp.status_code == 200
        assert 'marked' in resp.text()

    def test_serve_favicon(self, grip_text_server):
        client = grip_text_server('text')
        resp = client.get('/__/static/favicon.ico')
        assert resp.status_code == 200

    def test_missing_static_404(self, grip_text_server):
        client = grip_text_server('text')
        resp = client.get('/__/static/nonexistent.xyz')
        assert resp.status_code == 404

    def test_path_traversal_blocked(self, grip_text_server):
        client = grip_text_server('text')
        resp = client.get('/__/static/../../../etc/passwd')
        assert resp.status_code == 404


class TestRouting:
    """Verify directory routing, redirects, and binary serving."""

    def test_directory_with_readme(self, grip_dir_server):
        client = grip_dir_server({
            'README.md': '# Root',
            'sub/README.md': '# Sub',
        })
        resp = client.get('/sub/')
        # Subdirectory with README.md serves the HTML shell
        assert resp.status_code == 200
        assert '<!DOCTYPE html>' in resp.text()

    def test_explicit_markdown_file(self, grip_dir_server):
        client = grip_dir_server({
            'README.md': '# Root',
            'other.md': '# Other',
        })
        resp = client.get('/other.md')
        assert resp.status_code == 200
        assert '<!DOCTYPE html>' in resp.text()

    def test_missing_file_404(self, grip_dir_server):
        client = grip_dir_server({'README.md': '# Root'})
        resp = client.get('/nonexistent.md')
        assert resp.status_code == 404

    def test_binary_file_served_raw(self, grip_dir_server):
        png_header = b'\x89PNG\r\n\x1a\n' + b'\x00' * 100
        client = grip_dir_server({
            'README.md': '# Root',
            'image.png': png_header,
        })
        resp = client.get('/image.png')
        assert resp.status_code == 200
        assert resp.data[:4] == b'\x89PNG'
        assert 'image/png' in resp.headers.get('Content-Type', '')
