"""
E2E tests for the HTTP server — routes, content types, redirects, errors.
"""

import os


class TestPageRoutes:
    """HTML shell serving for markdown files."""

    def test_root_serves_html_shell(self, text_server):
        client = text_server("# Hello")
        resp = client.get("/")
        assert resp.status_code == 200
        assert "<!DOCTYPE html>" in resp.text()
        assert "markdraft-content" in resp.text()

    def test_page_has_data_attributes(self, text_server):
        client = text_server("# Hello")
        html = client.get("/").text()
        assert "data-content-url=" in html
        assert "data-color-mode=" in html

    def test_page_includes_script_tags(self, text_server):
        client = text_server("text")
        html = client.get("/").text()
        assert "marked.min.js" in html
        assert "marked-alert.umd.js" in html
        assert "highlight.min.js" in html
        assert "katex.min.js" in html
        assert "mermaid.min.js" in html
        assert "leaflet.js" in html
        assert "three.min.js" in html
        assert "marked-emoji.umd.js" in html
        assert "markdraft.js" in html

    def test_page_includes_css_links(self, text_server):
        client = text_server("text")
        html = client.get("/").text()
        assert "github-markdown-light.css" in html
        assert "katex.min.css" in html
        assert "leaflet.css" in html
        assert "markdraft.css" in html
        assert "octicons.css" in html


class TestPageTitle:
    def test_title_from_filename(self, text_server):
        client = text_server("# Hi", display_filename="README.md")
        assert "README.md - Markdraft" in client.get("/").text()

    def test_title_override(self, text_server):
        client = text_server("# Hi", title="Custom Title")
        assert "Custom Title" in client.get("/").text()

    def test_title_no_filename(self, text_server):
        client = text_server("# Hi", display_filename=None)
        html = client.get("/").text()
        assert "<title>Markdraft</title>" in html


class TestTheme:
    def test_theme_light(self, text_server):
        client = text_server("text", theme="light")
        html = client.get("/").text()
        assert 'data-color-mode="light"' in html
        assert "github-highlight.min.css" in html

    def test_theme_dark(self, text_server):
        client = text_server("text", theme="dark")
        html = client.get("/").text()
        assert 'data-color-mode="dark"' in html
        assert "github-highlight-dark.min.css" in html


class TestLayout:
    def test_readme_layout(self, text_server):
        client = text_server("text")
        html = client.get("/").text()
        assert 'id="readme"' in html
        assert "pull-discussion-timeline" not in html

    def test_user_content_layout(self, text_server):
        client = text_server("text", user_content=True)
        html = client.get("/").text()
        assert "pull-discussion-timeline" in html
        assert 'id="readme"' not in html

    def test_user_content_with_title(self, text_server):
        client = text_server("text", user_content=True, title="Issue #1")
        html = client.get("/").text()
        assert "timeline-comment-header" in html
        assert "Issue #1" in html

    def test_user_content_without_title_or_filename(self, text_server):
        client = text_server("text", user_content=True, display_filename=None)
        html = client.get("/").text()
        assert "pull-discussion-timeline" in html


class TestAutorefresh:
    def test_autorefresh_url_present(self, text_server):
        client = text_server("text", autorefresh=True)
        assert 'data-refresh-url="/__/api/refresh"' in client.get("/").text()

    def test_autorefresh_url_empty(self, text_server):
        client = text_server("text", autorefresh=False)
        assert 'data-refresh-url=""' in client.get("/").text()


class TestApiContent:
    """JSON content API."""

    def test_returns_json(self, text_server):
        client = text_server("# Hello")
        resp = client.get("/__/api/content")
        assert resp.status_code == 200
        assert "application/json" in resp.headers.get("Content-Type", "")

    def test_returns_raw_markdown(self, text_server):
        client = text_server("# Hello\n\n**bold**")
        data = client.get("/__/api/content").json()
        assert data["text"] == "# Hello\n\n**bold**"

    def test_returns_filename(self, text_server):
        client = text_server("text", display_filename="README.md")
        data = client.get("/__/api/content").json()
        assert data["filename"] == "README.md"

    def test_subpath(self, dir_server):
        client = dir_server({"README.md": "root", "other.md": "# Other"})
        data = client.get("/__/api/content/other.md").json()
        assert "# Other" in data["text"]

    def test_missing_file_404(self, text_server):
        assert text_server("text").get("/__/api/content/nope.md").status_code == 404


class TestApiRefresh:
    """SSE refresh endpoint."""

    def test_refresh_enabled_in_html(self, text_server):
        client = text_server("text", autorefresh=True)
        assert 'data-refresh-url="/__/api/refresh"' in client.get("/").text()

    def test_refresh_disabled_returns_404(self, text_server):
        assert (
            text_server("text", autorefresh=False).get("/__/api/refresh").status_code
            == 404
        )


class TestStaticFiles:
    def test_serve_bundled_css(self, text_server):
        resp = text_server("text").get("/__/static/markdraft.css")
        assert resp.status_code == 200
        assert ".preview-page" in resp.text()

    def test_serve_bundled_js(self, text_server):
        resp = text_server("text").get("/__/static/markdraft.js")
        assert resp.status_code == 200
        assert "marked" in resp.text()

    def test_serve_favicon(self, text_server):
        assert text_server("text").get("/__/static/favicon.ico").status_code == 200

    def test_serve_cached_asset(self, tmp_path, preview_server):
        from markdraft.assets import AssetCache
        from markdraft.readers import TextReader

        cache_path = str(tmp_path / "cache")
        os.makedirs(cache_path, exist_ok=True)
        with open(os.path.join(cache_path, "test-asset.js"), "w") as f:
            f.write("// cached asset")

        assets = AssetCache(cache_path)
        reader = TextReader("hi", "README.md")
        client = preview_server(reader, assets=assets)
        resp = client.get("/__/static/test-asset.js")
        assert resp.status_code == 200
        assert "// cached asset" in resp.text()

    def test_missing_static_404(self, text_server):
        assert text_server("text").get("/__/static/nope.xyz").status_code == 404

    def test_path_traversal_blocked(self, text_server):
        resp = text_server("text").get("/__/static/../../../etc/passwd")
        assert resp.status_code == 404

    def test_empty_filename_404(self, text_server):
        assert text_server("text").get("/__/static/").status_code == 404


class TestRouting:
    """Directory routing, redirects, binary serving."""

    def test_root_serves_readme(self, dir_server):
        resp = dir_server({"README.md": "# Root"}).get("/")
        assert resp.status_code == 200
        assert "<!DOCTYPE html>" in resp.text()

    def test_explicit_file(self, dir_server):
        client = dir_server({"README.md": "root", "other.md": "# Other"})
        assert client.get("/other.md").status_code == 200

    def test_missing_file_404(self, dir_server):
        assert dir_server({"README.md": "hi"}).get("/nope.md").status_code == 404

    def test_subdirectory_serves_readme(self, dir_server):
        client = dir_server({"README.md": "root", "sub/README.md": "sub"})
        assert client.get("/sub/").status_code == 200

    def test_binary_file_raw(self, dir_server):
        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 50
        client = dir_server({"README.md": "hi", "img.png": png})
        resp = client.get("/img.png")
        assert resp.status_code == 200
        assert resp.data[:4] == b"\x89PNG"
        assert "image/png" in resp.headers.get("Content-Type", "")

    def test_path_traversal_blocked(self, dir_server):
        assert (
            dir_server({"README.md": "hi"}).get("/../../../etc/passwd").status_code
            == 404
        )

    def test_directory_redirect(self, dir_server):
        client = dir_server({"README.md": "root", "sub/README.md": "sub"})
        resp = client.get("/sub")
        assert resp.status_code in (200, 302)


class TestDirectoryListing:
    """Directory browsing when no README is present."""

    def test_directory_without_readme_returns_200(self, dir_server):
        client = dir_server({"sub/guide.md": "# Guide"})
        resp = client.get("/sub/")
        assert resp.status_code == 200
        assert "<!DOCTYPE html>" in resp.text()

    def test_listing_api_returns_entries(self, dir_server):
        client = dir_server(
            {
                "docs/guide.md": "# Guide",
                "docs/api.md": "# API",
                "docs/sub/README.md": "# Sub",
            }
        )
        resp = client.get("/__/api/content/docs/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["type"] == "listing"
        names = [e["name"] for e in data["entries"]]
        assert "guide.md" in names
        assert "api.md" in names
        assert "sub" in names

    def test_listing_excludes_hidden_files(self, dir_server):
        client = dir_server(
            {
                "docs/.hidden.md": "secret",
                "docs/visible.md": "hi",
            }
        )
        resp = client.get("/__/api/content/docs/")
        data = resp.json()
        names = [e["name"] for e in data["entries"]]
        assert "visible.md" in names
        assert ".hidden.md" not in names

    def test_directory_with_readme_serves_readme(self, dir_server):
        client = dir_server({"README.md": "# Root"})
        resp = client.get("/__/api/content")
        data = resp.json()
        assert data["type"] == "file"
        assert "# Root" in data["text"]

    def test_root_without_readme_shows_listing(self, dir_server):
        client = dir_server({"docs/guide.md": "# Guide"})
        resp = client.get("/__/api/content")
        data = resp.json()
        assert data["type"] == "listing"
        names = [e["name"] for e in data["entries"]]
        assert "docs" in names

    def test_file_response_includes_siblings(self, dir_server):
        client = dir_server(
            {
                "README.md": "# Root",
                "guide.md": "# Guide",
                "other.md": "# Other",
            }
        )
        data = client.get("/__/api/content").json()
        assert data["type"] == "file"
        assert "siblings" in data
        names = [e["name"] for e in data["siblings"]]
        assert "guide.md" in names
        assert "other.md" in names

    def test_subdir_readme_siblings_are_subdir_contents(self, dir_server):
        client = dir_server(
            {
                "README.md": "# Root",
                "sub/README.md": "# Sub",
                "sub/api.md": "# API",
            }
        )
        data = client.get("/__/api/content/sub/").json()
        assert data["type"] == "file"
        names = [e["name"] for e in data["siblings"]]
        assert "api.md" in names
        assert "README.md" in names
