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
            "github-markdown.css",
            "github-highlight.min.css",
            "github-highlight-dark.min.css",
            "marked.min.js",
            "highlight.min.js",
            "mermaid.min.js",
        ]:
            with open(os.path.join(path, name), "w") as f:
                f.write("/* dummy {0} */".format(name))


class TestExport:

    def test_inline_produces_html(self, tmp_path):
        reader = TextReader("# Hello\n\n**bold**", "README.md")
        assets = MockAssetCache(str(tmp_path / "cache"))
        out = str(tmp_path / "out.html")
        export_page(reader, None, assets, out_file=out)
        with open(out) as f:
            html = f.read()
        assert "<!DOCTYPE html>" in html
        assert "# Hello" in html
        assert "**bold**" in html

    def test_inline_contains_scripts(self, tmp_path):
        reader = TextReader("text", "README.md")
        assets = MockAssetCache(str(tmp_path / "cache"))
        html = export_page(reader, None, assets)
        assert "/* dummy marked.min.js */" in html
        assert "/* dummy highlight.min.js */" in html
        assert "/* dummy mermaid.min.js */" in html

    def test_inline_contains_styles(self, tmp_path):
        reader = TextReader("text", "README.md")
        assets = MockAssetCache(str(tmp_path / "cache"))
        html = export_page(reader, None, assets)
        assert "/* dummy github-markdown.css */" in html

    def test_inline_contains_markdraft_js(self, tmp_path):
        reader = TextReader("text", "README.md")
        assets = MockAssetCache(str(tmp_path / "cache"))
        html = export_page(reader, None, assets)
        assert "markdraft-source" in html
        assert "marked.parse" in html

    def test_no_inline_uses_cdn_links(self, tmp_path):
        reader = TextReader("text", "README.md")
        assets = MockAssetCache(str(tmp_path / "cache"))
        html = export_page(reader, None, assets, inline=False)
        assert "cdn.jsdelivr.net" in html
        assert '<script src="https://' in html
        assert '<link rel="stylesheet" href="https://' in html

    def test_title_in_export(self, tmp_path):
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

    def test_markdown_with_script_tag_escaped(self, tmp_path):
        reader = TextReader("text</script>more", "README.md")
        assets = MockAssetCache(str(tmp_path / "cache"))
        html = export_page(reader, None, assets)
        # The </script in the markdown must be escaped
        assert "</script>more" not in html.split("markdraft-source")[1].split("</script")[0]
        assert "<\\/script" in html

    def test_export_to_stdout(self, tmp_path, capsys):
        reader = TextReader("# Stdout", "README.md")
        assets = MockAssetCache(str(tmp_path / "cache"))
        export_page(reader, None, assets, out_file="-")
        captured = capsys.readouterr()
        assert "<!DOCTYPE html>" in captured.out
        assert "# Stdout" in captured.out

    def test_user_content_layout(self, tmp_path):
        reader = TextReader("text", "README.md")
        assets = MockAssetCache(str(tmp_path / "cache"))
        html = export_page(reader, None, assets, user_content=True)
        assert "pull-discussion-timeline" in html
        assert 'id="readme"' not in html
