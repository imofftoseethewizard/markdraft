"""
Component tests for GripperRenderer and OfflineRenderer.

Tests mermaid block extraction, placeholder substitution, and base
offline rendering.
"""
from __future__ import print_function, unicode_literals

import pytest

from grip import GripperRenderer, OfflineRenderer
from grip.mermaid import MERMAID_BLOCK_RE


# ===========================================================================
# Mermaid block extraction (regex)
# ===========================================================================

class TestMermaidExtraction:
    """Test the MERMAID_BLOCK_RE regex and extraction phase."""

    def test_extract_single_block(self):
        r = GripperRenderer()
        html = r.render('```mermaid\ngraph LR\n    A-->B\n```')
        assert '<pre class="mermaid">' in html
        assert 'graph LR' in html

    def test_extract_multiple_blocks(self):
        md = '```mermaid\nAAA\n```\n\n```mermaid\nBBB\n```'
        r = GripperRenderer()
        html = r.render(md)
        assert html.count('<pre class="mermaid">') == 2
        assert 'AAA' in html
        assert 'BBB' in html

    def test_extract_no_blocks(self):
        r = GripperRenderer()
        html = r.render('# Just a heading')
        assert '<pre class="mermaid">' not in html

    def test_extract_four_backticks(self):
        md = '````mermaid\ncontent\n````'
        r = GripperRenderer()
        html = r.render(md)
        assert '<pre class="mermaid">' in html
        assert 'content' in html

    def test_non_mermaid_fenced_block(self):
        r = GripperRenderer()
        html = r.render('```python\nprint(1)\n```')
        assert '<pre class="mermaid">' not in html

    def test_mermaid_case_sensitive(self):
        r = GripperRenderer()
        html = r.render('```Mermaid\ncontent\n```')
        assert '<pre class="mermaid">' not in html

    def test_empty_mermaid_block(self):
        r = GripperRenderer()
        html = r.render('```mermaid\n```')
        assert '<pre class="mermaid">' in html

    def test_mermaid_with_trailing_spaces(self):
        md = '```mermaid   \ncontent\n```'
        r = GripperRenderer()
        html = r.render(md)
        assert '<pre class="mermaid">' in html

    def test_mermaid_block_escapes_html(self):
        md = '```mermaid\nA --> B<script>alert(1)</script>\n```'
        r = GripperRenderer()
        html = r.render(md)
        assert '<pre class="mermaid">' in html
        assert '&lt;script&gt;' in html
        assert '<script>alert(1)</script>' not in html

    def test_mixed_content_ordering(self):
        md = 'Before\n\n```mermaid\nAAA\n```\n\nMiddle\n\n```mermaid\nBBB\n```\n\nAfter'
        r = GripperRenderer()
        html = r.render(md)
        pos_before = html.index('Before')
        pos_aaa = html.index('AAA')
        pos_middle = html.index('Middle')
        pos_bbb = html.index('BBB')
        pos_after = html.index('After')
        assert pos_before < pos_aaa < pos_middle < pos_bbb < pos_after


# ===========================================================================
# Placeholder substitution
# ===========================================================================

class TestPlaceholderSubstitution:
    """Test the post-rendering substitution of placeholders."""

    def test_placeholder_in_p_tags(self):
        """Mermaid block alone in a paragraph — <p> wrapper removed."""
        r = GripperRenderer()
        html = r.render('```mermaid\ngraph LR\n    A-->B\n```')
        assert '<p><pre class="mermaid">' not in html
        assert '<pre class="mermaid">' in html

    def test_placeholder_bare(self):
        """All placeholders replaced, none left in output."""
        r = GripperRenderer()
        html = r.render('```mermaid\ngraph LR\n    A-->B\n```')
        assert 'GRIPPER_MERMAID' not in html

    def test_placeholder_with_whitespace(self):
        r = GripperRenderer()
        html = r.render('```mermaid\ngraph LR\n    A-->B\n```')
        assert 'GRIPPER_MERMAID' not in html

    def test_multiple_placeholders(self):
        md = '```mermaid\nAAA\n```\n\n```mermaid\nBBB\n```'
        r = GripperRenderer()
        html = r.render(md)
        assert html.count('<pre class="mermaid">') == 2
        assert 'GRIPPER_MERMAID' not in html


# ===========================================================================
# OfflineRenderer base rendering
# ===========================================================================

class TestOfflineRenderer:
    """Tests for the base OfflineRenderer.render() method."""

    def test_offline_render_basic(self):
        r = OfflineRenderer()
        html = r.render('**bold**')
        assert '<strong>bold</strong>' in html

    def test_offline_render_fenced_code(self):
        r = OfflineRenderer()
        html = r.render('```python\nx = 1\n```')
        assert 'highlight' in html
        assert '<code>' in html or '<code ' in html

    def test_offline_render_table(self):
        r = OfflineRenderer()
        html = r.render('| A | B |\n|---|---|\n| 1 | 2 |')
        assert '<table>' in html
        assert '<td>' in html or '<td' in html

    def test_offline_render_toc_ids(self):
        r = OfflineRenderer()
        html = r.render('# Heading')
        assert '<h1 id="heading">' in html

    def test_offline_render_urlize(self):
        r = OfflineRenderer()
        html = r.render('Visit http://example.com today')
        assert '<a href="http://example.com">' in html

    def test_offline_render_codehilite(self):
        r = OfflineRenderer()
        html = r.render('```python\ndef foo():\n    pass\n```')
        assert 'highlight' in html

    def test_offline_render_empty(self):
        r = OfflineRenderer()
        html = r.render('')
        assert html == ''
