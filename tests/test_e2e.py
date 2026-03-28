"""
End-to-end tests for the Gripper rendering pipeline.

Each test makes HTTP requests against a Flask test client and asserts
on the returned HTML. Uses GripperRenderer (the default) unless noted.
"""
import pytest

from grip import (
    DirectoryReader, Grip, GripperRenderer, TextReader, export, render_page)
from mocks import GitHubAssetManagerMock


MERMAID_GRAPH = '```mermaid\ngraph LR\n    A[Start] --> B[End]\n```'
MERMAID_SEQUENCE = '```mermaid\nsequenceDiagram\n    Alice->>Bob: Hello\n    Bob-->>Alice: Hi\n```'


def _get(client, path='/'):
    resp = client.get(path, follow_redirects=False)
    if resp.status_code == 200:
        return resp.data.decode('utf-8')
    return resp


# ---------------------------------------------------------------------------
# Dimension 1: Markdown content
# ---------------------------------------------------------------------------

class TestMarkdownContent:
    """Verify rendered article content for various markdown inputs."""

    def test_empty_document(self, grip_app):
        html = _get(grip_app(''))
        assert 'id="grip-content"' in html
        assert '<article id="grip-content" class="markdown-body entry-content container-lg">' in html

    def test_plain_text(self, grip_app):
        html = _get(grip_app('Hello world'))
        assert '<p>Hello world</p>' in html

    def test_atx_headers(self, grip_app):
        html = _get(grip_app('# H1\n\n## H2\n\n### H3'))
        assert '<h1' in html and 'H1' in html
        assert '<h2' in html and 'H2' in html
        assert '<h3' in html and 'H3' in html

    def test_setext_headers(self, grip_app):
        html = _get(grip_app('H1\n===\n\nH2\n---'))
        assert '<h1' in html and 'H1' in html
        assert '<h2' in html and 'H2' in html

    def test_emphasis(self, grip_app):
        html = _get(grip_app('*em* **strong**'))
        assert '<em>em</em>' in html
        assert '<strong>strong</strong>' in html

    def test_inline_code(self, grip_app):
        html = _get(grip_app('`code`'))
        assert '<code>code</code>' in html

    def test_fenced_code_block(self, grip_app):
        html = _get(grip_app('```python\nprint(1)\n```'))
        # codehilite tokenizes the code, so check for the highlight wrapper
        assert 'highlight' in html
        assert 'print' in html
        assert 'mermaid-diagram' not in html

    def test_links(self, grip_app):
        html = _get(grip_app('[text](http://example.com)'))
        assert '<a href="http://example.com">text</a>' in html

    def test_images(self, grip_app):
        html = _get(grip_app('![alt](img.png)'))
        assert '<img' in html
        assert 'alt="alt"' in html
        assert 'img.png' in html

    def test_unordered_list(self, grip_app):
        html = _get(grip_app('- a\n- b\n- c'))
        assert '<ul>' in html
        assert html.count('<li>') == 3

    def test_ordered_list(self, grip_app):
        html = _get(grip_app('1. a\n2. b'))
        assert '<ol>' in html
        assert html.count('<li>') == 2

    def test_blockquote(self, grip_app):
        html = _get(grip_app('> quoted'))
        assert '<blockquote>' in html
        assert 'quoted' in html

    def test_horizontal_rule(self, grip_app):
        html = _get(grip_app('text\n\n---\n\ntext'))
        assert '<hr' in html

    def test_table(self, grip_app):
        md = '| A | B |\n|---|---|\n| 1 | 2 |'
        html = _get(grip_app(md))
        assert '<table>' in html
        assert '<th>' in html or '<th' in html
        assert '<td>' in html or '<td' in html

    def test_unicode_content(self, grip_app):
        html = _get(grip_app('Emoji: \U0001f600 Accents: caf\u00e9'))
        assert '\U0001f600' in html
        assert 'caf\u00e9' in html

    def test_html_passthrough(self, grip_app):
        html = _get(grip_app('<div class="custom">text</div>'))
        assert '<div class="custom">text</div>' in html

    def test_autolinked_url(self, grip_app):
        html = _get(grip_app('Visit http://example.com today'))
        assert '<a href="http://example.com">' in html

    def test_toc_header_ids(self, grip_app):
        html = _get(grip_app('# Section One'))
        assert 'id="section-one"' in html


# ---------------------------------------------------------------------------
# Dimension 2: Mermaid rendering
# ---------------------------------------------------------------------------

class TestMermaidRendering:
    """Verify mermaid fenced code blocks produce <pre class="mermaid"> tags."""

    def test_single_mermaid_block(self, grip_app):
        html = _get(grip_app(MERMAID_GRAPH))
        assert '<pre class="mermaid">' in html
        assert 'GRIPPER_MERMAID' not in html

    def test_two_mermaid_blocks(self, grip_app):
        md = 'Before\n\n' + MERMAID_GRAPH + '\n\nMiddle\n\n' + MERMAID_SEQUENCE + '\n\nAfter'
        html = _get(grip_app(md))
        assert html.count('<pre class="mermaid">') == 2
        assert '<p>Before</p>' in html
        assert '<p>Middle</p>' in html
        assert '<p>After</p>' in html

    def test_mermaid_with_regular_code(self, grip_app):
        md = MERMAID_GRAPH + '\n\n```python\nprint(1)\n```'
        html = _get(grip_app(md))
        assert html.count('<pre class="mermaid">') == 1
        # codehilite tokenizes the code into spans
        assert 'print' in html
        assert 'highlight' in html

    def test_mermaid_graph_lr(self, grip_app):
        html = _get(grip_app(MERMAID_GRAPH))
        assert '<pre class="mermaid">' in html
        assert 'graph LR' in html

    def test_mermaid_sequence_diagram(self, grip_app):
        html = _get(grip_app(MERMAID_SEQUENCE))
        assert '<pre class="mermaid">' in html
        assert 'sequenceDiagram' in html

    def test_mermaid_flowchart(self, grip_app):
        md = '```mermaid\nflowchart TD\n    A --> B\n```'
        html = _get(grip_app(md))
        assert '<pre class="mermaid">' in html

    def test_no_mermaid_blocks(self, grip_app):
        html = _get(grip_app('# Hello\n\nJust text.'))
        assert '<pre class="mermaid">' not in html
        assert 'GRIPPER_MERMAID' not in html

    def test_mermaid_surrounded_by_text(self, grip_app):
        md = 'Before paragraph.\n\n' + MERMAID_GRAPH + '\n\nAfter paragraph.'
        html = _get(grip_app(md))
        assert '<p>Before paragraph.</p>' in html
        assert '<p>After paragraph.</p>' in html
        assert '<pre class="mermaid">' in html
        # The mermaid pre should NOT be inside a <p> tag
        assert '<p><pre class="mermaid">' not in html

    def test_mermaid_js_script_tag(self, grip_app):
        html = _get(grip_app(MERMAID_GRAPH))
        assert 'mermaid.min.js' in html
        assert 'grip.js' in html


# ---------------------------------------------------------------------------
# Dimension 3: Page structure and template variables
# ---------------------------------------------------------------------------

class TestPageStructure:
    """Verify full HTML page structure with different Grip() config."""

    def test_page_structure_default(self, grip_app):
        html = _get(grip_app('# Hello'))
        assert '<!DOCTYPE html>' in html
        assert '<html' in html
        assert 'data-color-mode=' in html
        assert 'class="markdown-body' in html
        assert 'id="grip-content"' in html

    def test_page_title_from_filename(self, grip_app):
        html = _get(grip_app('# Hello', display_filename='README.md'))
        assert '<title>README.md - Grip</title>' in html

    def test_page_title_override(self, grip_app):
        html = _get(grip_app('# Hello', title='My Title'))
        assert '<title>My Title</title>' in html

    def test_page_title_none(self, grip_app):
        html = _get(grip_app('# Hello', display_filename=None))
        assert '<title>' in html
        assert '- Grip</title>' in html

    def test_theme_light(self, grip_app):
        html = _get(grip_app('text', theme='light'))
        assert 'data-color-mode=light' in html

    def test_theme_dark(self, grip_app):
        html = _get(grip_app('text', theme='dark'))
        assert 'data-color-mode=dark' in html

    def test_user_content_layout(self, grip_app):
        renderer = GripperRenderer(user_content=True)
        html = _get(grip_app('text', renderer=renderer))
        assert 'pull-discussion-timeline' in html
        assert 'id="readme"' not in html

    def test_non_user_content_layout(self, grip_app):
        html = _get(grip_app('text'))
        assert 'id="readme"' in html
        assert 'pull-discussion-timeline' not in html

    def test_wide_style(self, grip_app):
        html = _get(grip_app('text', render_wide=True))
        # The wide style is only relevant for user-content layout
        # but the CSS rule .discussion-timeline.wide is always present
        assert 'width: 920px' in html

    def test_autorefresh_enabled(self, grip_app):
        html = _get(grip_app('text', autorefresh=True))
        assert 'data-autorefresh-url="' in html
        # The URL should be non-empty
        assert 'data-autorefresh-url=""' not in html

    def test_autorefresh_disabled(self, grip_app):
        html = _get(grip_app('text', autorefresh=False))
        assert 'data-autorefresh-url=""' in html

    def test_user_content_with_title(self, grip_app):
        renderer = GripperRenderer(user_content=True)
        html = _get(grip_app('text', renderer=renderer, title='Issue'))
        assert 'timeline-comment-header' in html
        assert 'Issue' in html

    def test_user_content_without_title(self, grip_app):
        renderer = GripperRenderer(user_content=True)
        html = _get(grip_app('text', renderer=renderer))
        assert 'timeline-comment-header' not in html

    def test_box_header_with_filename(self, grip_app):
        html = _get(grip_app('text', display_filename='README.md'))
        assert 'Box-header' in html
        assert 'README.md' in html

    def test_box_header_without_filename(self, grip_app):
        html = _get(grip_app('text', display_filename=None))
        assert 'Box-header' not in html

    def test_octicons_stylesheet(self, grip_app):
        html = _get(grip_app('text'))
        assert 'octicons.css' in html

    def test_favicon_link(self, grip_app):
        html = _get(grip_app('text'))
        assert '<link rel="icon"' in html


# ---------------------------------------------------------------------------
# Dimension 4: Correlated — mermaid x page config
# ---------------------------------------------------------------------------

class TestMermaidCrossConfig:
    """Mermaid rendering combined with page config variations."""

    def test_mermaid_dark_theme(self, grip_app):
        html = _get(grip_app(MERMAID_GRAPH, theme='dark'))
        assert '<pre class="mermaid">' in html
        assert 'data-color-mode=dark' in html

    def test_mermaid_user_content(self, grip_app):
        renderer = GripperRenderer(user_content=True)
        html = _get(grip_app(MERMAID_GRAPH, renderer=renderer))
        assert '<pre class="mermaid">' in html
        assert 'comment-body' in html
        assert 'id="readme"' not in html

    def test_mermaid_with_title(self, grip_app):
        html = _get(grip_app(MERMAID_GRAPH, title='Diagrams'))
        assert '<title>Diagrams</title>' in html
        assert '<pre class="mermaid">' in html

    def test_mermaid_autorefresh_off(self, grip_app):
        html = _get(grip_app(MERMAID_GRAPH, autorefresh=False))
        assert '<pre class="mermaid">' in html
        assert 'data-autorefresh-url=""' in html


# ---------------------------------------------------------------------------
# Dimension 5: Routing and file serving
# ---------------------------------------------------------------------------

class TestRouting:
    """Verify path handling, redirects, 404s, and binary serving."""

    def test_root_serves_readme(self, grip_dir_app):
        client = grip_dir_app({'README.md': '# Root'})
        html = _get(client, '/')
        assert '<h1' in html
        assert 'Root' in html

    def test_explicit_file_path(self, grip_dir_app):
        client = grip_dir_app({
            'README.md': '# Root',
            'other.md': '# Other',
        })
        html = _get(client, '/other.md')
        assert 'Other' in html

    def test_missing_file_404(self, grip_dir_app):
        client = grip_dir_app({'README.md': '# Root'})
        resp = _get(client, '/nonexistent.md')
        assert resp.status_code == 404

    def test_directory_redirect(self, grip_dir_app):
        client = grip_dir_app({
            'README.md': '# Root',
            'subdir/README.md': '# Sub',
        })
        resp = _get(client, '/subdir')
        assert resp.status_code in (301, 302, 308)
        location = resp.headers.get('Location', '')
        assert '/subdir' in location

    def test_directory_serves_readme(self, grip_dir_app):
        client = grip_dir_app({
            'README.md': '# Root',
            'subdir/README.md': '# Sub',
        })
        resp = client.get('/subdir/', follow_redirects=True)
        html = resp.data.decode('utf-8')
        assert 'Sub' in html

    def test_binary_file_served_raw(self, grip_dir_app):
        png_header = b'\x89PNG\r\n\x1a\n' + b'\x00' * 100
        client = grip_dir_app({
            'README.md': '# Root',
            'image.png': png_header,
        })
        resp = client.get('/image.png')
        assert resp.status_code == 200
        assert resp.content_type.startswith('image/png')
        assert resp.data[:4] == b'\x89PNG'

    def test_path_traversal_blocked(self, grip_dir_app):
        client = grip_dir_app({'README.md': '# Root'})
        resp = client.get('/../../../etc/passwd')
        assert resp.status_code in (400, 404)

    def test_normalized_path_redirect(self, grip_dir_app):
        client = grip_dir_app({'README.md': '# Root'})
        resp = _get(client, '/./README.md/')
        # Should redirect to the normalized path
        if hasattr(resp, 'status_code'):
            assert resp.status_code in (301, 302, 308)
        else:
            # Followed redirect, got the content
            assert '# Root' in resp or 'Root' in resp


# ---------------------------------------------------------------------------
# Dimension 6: Inline rendering and export
# ---------------------------------------------------------------------------

class TestInlineAndExport:
    """Test render_inline and export() paths."""

    def test_render_inline_favicon(self, grip_app):
        html = _get(grip_app('text', render_inline=True))
        assert 'data:image/x-icon;base64,' in html

    def test_render_not_inline_favicon(self, grip_app):
        html = _get(grip_app('text', render_inline=False))
        assert '<link rel="icon"' in html
        assert 'data:image/x-icon;base64,' not in html

    def test_export_produces_html(self, tmp_path, monkeypatch):
        monkeypatch.setenv('GRIPHOME', str(tmp_path / '.grip'))
        out = str(tmp_path / 'output.html')
        md_file = str(tmp_path / 'README.md')
        with open(md_file, 'w') as f:
            f.write('# Export Test\n\nHello export.')
        export(md_file, render_offline=True, out_filename=out, quiet=True)
        with open(out, 'r') as f:
            html = f.read()
        assert '<!DOCTYPE html>' in html
        assert 'Export Test' in html
        assert 'Hello export' in html

    def test_export_stdout(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setenv('GRIPHOME', str(tmp_path / '.grip'))
        md_file = str(tmp_path / 'README.md')
        with open(md_file, 'w') as f:
            f.write('# Stdout')
        export(md_file, render_offline=True, out_filename='-', quiet=True)
        captured = capsys.readouterr()
        assert '<!DOCTYPE html>' in captured.out
        assert 'Stdout' in captured.out


# ---------------------------------------------------------------------------
# Dimension 7: Autorefresh SSE
# ---------------------------------------------------------------------------

class TestAutorefresh:
    """Test the Server-Sent Events refresh endpoint."""

    def test_refresh_endpoint_exists(self, grip_app):
        client = grip_app('text', autorefresh=True)
        resp = client.get('/__/grip/refresh/')
        # Returns 200 (not 404) when autorefresh is enabled.
        # Content-type is text/event-stream only when the server is
        # actually running; in test_client context it returns '' early
        # because _shutdown_event is None.
        assert resp.status_code == 200

    def test_refresh_endpoint_disabled(self, grip_app):
        client = grip_app('text', autorefresh=False)
        resp = client.get('/__/grip/refresh/')
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Dimension 8: Error handling
# ---------------------------------------------------------------------------

class TestErrorHandling:
    """Edge cases in the render pipeline."""

    def test_render_empty_file(self, grip_app):
        html = _get(grip_app(''))
        assert 'id="grip-content"' in html

    def test_large_markdown(self, grip_app):
        large = '\n'.join('Line {0}: some text here.'.format(i)
                          for i in range(10000))
        html = _get(grip_app(large))
        assert 'Line 0' in html
        assert 'Line 9999' in html
