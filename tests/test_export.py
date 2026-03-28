"""
Tests for HTML export.
"""

import os

from markdraft.assets import AssetCache
from markdraft.export import export_page
from markdraft.readers import TextReader


class MockAssetCache(AssetCache):
    """Asset cache with dummy files for testing."""

    def __init__(self, path):
        super().__init__(path)
        os.makedirs(path, exist_ok=True)
        for name in [
            "github-markdown-light.css",
            "github-markdown-dark.css",
            "github-highlight.min.css",
            "github-highlight-dark.min.css",
            "marked.min.js",
            "marked-alert.umd.js",
            "highlight.min.js",
            "katex.min.js",
            "marked-katex-extension.umd.js",
            "mermaid.min.js",
            "leaflet.js",
            "leaflet.css",
            "three.min.js",
        ]:
            with open(os.path.join(path, name), "w") as f:
                f.write("/* dummy {0} */".format(name))


class TestInlineExport:
    def test_contains_css(self, tmp_path):
        reader = TextReader("text", "README.md")
        assets = MockAssetCache(str(tmp_path / "cache"))
        html = export_page(reader, None, assets)
        assert "/* dummy github-markdown-light.css */" in html

    def test_contains_js(self, tmp_path):
        reader = TextReader("text", "README.md")
        assets = MockAssetCache(str(tmp_path / "cache"))
        html = export_page(reader, None, assets)
        assert "/* dummy marked.min.js */" in html
        assert "/* dummy highlight.min.js */" in html
        assert "/* dummy katex.min.js */" in html
        assert "/* dummy marked-alert.umd.js */" in html
        assert "/* dummy mermaid.min.js */" in html

    def test_contains_markdraft_js(self, tmp_path):
        reader = TextReader("text", "README.md")
        assets = MockAssetCache(str(tmp_path / "cache"))
        html = export_page(reader, None, assets)
        assert "markdraft-source" in html
        assert "marked.parse" in html

    def test_inline_includes_katex_css_link(self, tmp_path):
        """KaTeX CSS is always from CDN even in inline mode (font URLs)."""
        reader = TextReader("text", "README.md")
        assets = MockAssetCache(str(tmp_path / "cache"))
        html = export_page(reader, None, assets)
        assert "katex.min.css" in html


class TestCdnExport:
    def test_has_cdn_links(self, tmp_path):
        reader = TextReader("text", "README.md")
        assets = MockAssetCache(str(tmp_path / "cache"))
        html = export_page(reader, None, assets, inline=False)
        assert "cdn.jsdelivr.net" in html
        assert '<script src="https://' in html
        assert '<link rel="stylesheet" href="https://' in html


class TestMarkdownEmbedding:
    def test_markdown_in_source_tag(self, tmp_path):
        reader = TextReader("# Hello\n\n**bold**", "README.md")
        assets = MockAssetCache(str(tmp_path / "cache"))
        html = export_page(reader, None, assets)
        assert "# Hello" in html
        assert "**bold**" in html

    def test_script_tag_escaped(self, tmp_path):
        reader = TextReader("text</script>more", "README.md")
        assets = MockAssetCache(str(tmp_path / "cache"))
        html = export_page(reader, None, assets)
        assert "<\\/script" in html
        # Verify the </script> in markdown doesn't break the tag
        source_section = html.split("markdraft-source")[1].split("</script")[0]
        assert "</script>more" not in source_section

    def test_script_tag_case_insensitive(self, tmp_path):
        reader = TextReader("text</ScRiPt><script>alert(1)</script>end", "README.md")
        assets = MockAssetCache(str(tmp_path / "cache"))
        html = export_page(reader, None, assets)
        # Case-insensitive </script> variants must all be escaped
        source_section = html.split("markdraft-source")[1].split("</script")[0]
        assert "</ScRiPt>" not in source_section


class TestExportMetadata:
    def test_title(self, tmp_path):
        reader = TextReader("text", "README.md")
        assets = MockAssetCache(str(tmp_path / "cache"))
        html = export_page(reader, None, assets, title="My Page")
        assert "<title>My Page</title>" in html

    def test_dark_theme(self, tmp_path):
        reader = TextReader("text", "README.md")
        assets = MockAssetCache(str(tmp_path / "cache"))
        html = export_page(reader, None, assets, theme="dark")
        assert 'data-color-mode="dark"' in html
        assert "github-highlight-dark" in html

    def test_light_theme_default(self, tmp_path):
        reader = TextReader("text", "README.md")
        assets = MockAssetCache(str(tmp_path / "cache"))
        html = export_page(reader, None, assets)
        assert 'data-color-mode="light"' in html


class TestExportLayout:
    def test_readme_layout(self, tmp_path):
        reader = TextReader("text", "README.md")
        assets = MockAssetCache(str(tmp_path / "cache"))
        html = export_page(reader, None, assets)
        assert 'id="readme"' in html
        assert "pull-discussion-timeline" not in html

    def test_user_content_layout(self, tmp_path):
        reader = TextReader("text", "README.md")
        assets = MockAssetCache(str(tmp_path / "cache"))
        html = export_page(reader, None, assets, user_content=True)
        assert "pull-discussion-timeline" in html
        assert 'id="readme"' not in html


class TestExportOutput:
    def test_to_file(self, tmp_path):
        reader = TextReader("# Test", "README.md")
        assets = MockAssetCache(str(tmp_path / "cache"))
        out = str(tmp_path / "out.html")
        export_page(reader, None, assets, out_file=out)
        with open(out) as f:
            html = f.read()
        assert "<!DOCTYPE html>" in html

    def test_to_stdout(self, tmp_path, capsys):
        reader = TextReader("# Stdout", "README.md")
        assets = MockAssetCache(str(tmp_path / "cache"))
        export_page(reader, None, assets, out_file="-")
        captured = capsys.readouterr()
        assert "<!DOCTYPE html>" in captured.out

    def test_returns_string(self, tmp_path):
        reader = TextReader("# Test", "README.md")
        assets = MockAssetCache(str(tmp_path / "cache"))
        html = export_page(reader, None, assets)
        assert isinstance(html, str)
        assert "<!DOCTYPE html>" in html
