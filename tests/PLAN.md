# Test Plan

## Approach

Tests are organized into two categories:

1. **E2E tests** (`test_e2e.py`) — HTTP requests against a live Flask test
   client. Assertions on the returned HTML. This is the primary test surface.
2. **Component tests** (`test_mermaid.py`) — Unit tests for
   `GripperRenderer` and its mermaid extraction/rendering logic, which is
   the only complex algorithmic code in the project.

Existing test files (`test_api.py`, `test_cli.py`) are left unchanged.
They already cover the GitHub API rendering path and basic CLI behavior.
The new tests cover the offline/mermaid rendering path that gripper
actually uses.

### Coverage target

Line coverage of all code reachable through the `GripperRenderer` path
(the default). Catch-all exception handlers (bare `except Exception`)
are excluded from the coverage target but are tested where feasible via
mocking.

### Semantic dimensions

The input space is decomposed into orthogonal dimensions. Each dimension
is sampled across its equivalence classes. Correlated dimensions that
interact are tested combinatorially where the interaction could cause
bugs; independent dimensions are tested in isolation.

---

## E2E Tests — `test_e2e.py`

Every test creates a `Grip` app with `GripperRenderer` (the default),
a `GitHubAssetManagerMock`, and uses `app.test_client()` for HTTP GETs.
Assertions inspect the response status code and parse/search the HTML body.

### Fixtures

```
fixture: grip_app(tmp_path, markdown_text, **kwargs)
  Creates a Grip app with a TextReader for the given markdown,
  GripperRenderer, and GitHubAssetManagerMock.
  kwargs forwarded to Grip() (render_wide, render_inline, title,
  autorefresh, quiet, theme).
  Returns Flask test_client.

fixture: grip_dir_app(tmp_path, files_dict, **kwargs)
  Creates a Grip app with a DirectoryReader pointed at tmp_path.
  files_dict is {filename: content} written to tmp_path.
  Returns Flask test_client.
```

### Dimension 1: Markdown content (orthogonal to app config)

These tests verify the rendered `<article>` content is correct for
various markdown inputs. Each test GETs `/` and inspects the HTML
inside `#grip-content`.

| ID  | Test                     | Input                                     | Assertions                                             |
|-----|--------------------------|-------------------------------------------|--------------------------------------------------------|
| E1  | `test_empty_document`    | `""`                                      | 200, `#grip-content` exists, article is empty          |
| E2  | `test_plain_text`        | `"Hello world"`                           | `<p>Hello world</p>` in content                        |
| E3  | `test_atx_headers`       | `# H1\n## H2\n### H3`                     | `<h1`, `<h2`, `<h3` present with correct text          |
| E4  | `test_setext_headers`    | `H1\n===\n\nH2\n---`                      | `<h1` and `<h2` present                                |
| E5  | `test_emphasis`          | `*em* **strong** ***both***`              | `<em>`, `<strong>` tags                                |
| E6  | `test_inline_code`       | `` `code` ``                              | `<code>code</code>`                                    |
| E7  | `test_fenced_code_block` | ` ```python\nprint(1)\n``` `              | `<code` with content, NOT treated as mermaid           |
| E8  | `test_links`             | `[text](http://example.com)`              | `<a href="http://example.com">text</a>`                |
| E9  | `test_images`            | `![alt](img.png)`                         | `<img` with `alt="alt"` and `src` containing `img.png` |
| E10 | `test_unordered_list`    | `- a\n- b\n- c`                           | `<ul>` with 3 `<li>`                                   |
| E11 | `test_ordered_list`      | `1. a\n2. b`                              | `<ol>` with 2 `<li>`                                   |
| E12 | `test_blockquote`        | `> quoted`                                | `<blockquote>` with content                            |
| E13 | `test_horizontal_rule`   | `text\n\n---\n\ntext`                     | `<hr` present                                          |
| E14 | `test_table`             | GFM table with header and rows            | `<table>`, `<th>`, `<td>`                              |
| E15 | `test_unicode_content`   | `"Emoji: \U0001f600 Accents: cafe\u0301"` | Characters preserved in output                         |
| E16 | `test_html_passthrough`  | `<div class="custom">text</div>`          | div preserved in output                                |
| E17 | `test_autolinked_url`    | `Visit http://example.com today`          | `<a href="http://example.com">` (via UrlizeExtension)  |
| E18 | `test_toc_header_ids`    | `# Section One`                           | `id=` attribute on `<h1>` (via toc extension)          |

### Dimension 2: Mermaid rendering (orthogonal to other markdown)

Tests that mermaid fenced code blocks produce SVG diagrams.

| ID  | Test                              | Input                                       | Assertions                                                                                 |
|-----|-----------------------------------|---------------------------------------------|--------------------------------------------------------------------------------------------|
| E20 | `test_single_mermaid_block`       | One ` ```mermaid ` block                    | `<div class="mermaid-diagram">` present, `<svg` present, no placeholder text in output     |
| E21 | `test_two_mermaid_blocks`         | Two mermaid blocks with text between        | Two `mermaid-diagram` divs, two `<svg` elements, surrounding `<p>` text preserved          |
| E22 | `test_mermaid_with_regular_code`  | One mermaid block + one ` ```python ` block | One `mermaid-diagram`, python code block NOT rendered as SVG                               |
| E23 | `test_mermaid_graph_lr`           | `graph LR\n  A-->B`                         | SVG output, no errors                                                                      |
| E24 | `test_mermaid_sequence_diagram`   | `sequenceDiagram\n  A->>B: Hello`           | SVG output                                                                                 |
| E25 | `test_mermaid_flowchart`          | `flowchart TD\n  A-->B`                     | SVG output                                                                                 |
| E26 | `test_no_mermaid_blocks`          | Regular markdown only                       | No `mermaid-diagram` in output, no placeholder strings                                     |
| E27 | `test_mermaid_surrounded_by_text` | Paragraph, mermaid, paragraph               | `<p>` before and after the `<div class="mermaid-diagram">`, mermaid div NOT inside a `<p>` |

### Dimension 3: Page structure and template variables

These test the full HTML page structure, not just the content. They
verify template rendering with different `Grip()` constructor args.

| ID  | Test                               | Config                               | Assertions on full HTML                                                                                                  |
|-----|------------------------------------|--------------------------------------|--------------------------------------------------------------------------------------------------------------------------|
| E30 | `test_page_structure_default`      | defaults                             | `<!DOCTYPE html>`, `<html`, `data-color-mode`, `<title>` contains filename, `class="markdown-body"`, `id="grip-content"` |
| E31 | `test_page_title_from_filename`    | path to `README.md`                  | `<title>README.md - Grip</title>`                                                                                        |
| E32 | `test_page_title_override`         | `title="My Title"`                   | `<title>My Title</title>`                                                                                                |
| E33 | `test_page_title_none`             | TextReader with no filename          | `<title> - Grip</title>` (empty filename)                                                                                |
| E34 | `test_theme_light`                 | `theme='light'`                      | `data-color-mode=light`                                                                                                  |
| E35 | `test_theme_dark`                  | `theme='dark'`                       | `data-color-mode=dark`                                                                                                   |
| E36 | `test_user_content_layout`         | `user_content=True` on renderer      | `class="pull-discussion-timeline"` present, `id="readme"` absent                                                         |
| E37 | `test_non_user_content_layout`     | default                              | `id="readme"` present, `pull-discussion-timeline` absent                                                                 |
| E38 | `test_wide_style`                  | `render_wide=True`                   | CSS class or style for wide rendering present                                                                            |
| E39 | `test_autorefresh_enabled`         | `autorefresh=True`                   | `data-autorefresh-url` attribute is non-empty                                                                            |
| E40 | `test_autorefresh_disabled`        | `autorefresh=False`                  | `data-autorefresh-url` attribute is empty                                                                                |
| E41 | `test_user_content_with_title`     | `user_content=True`, `title="Issue"` | Title appears in `.timeline-comment-header`                                                                              |
| E42 | `test_user_content_without_title`  | `user_content=True`, no title        | No `.timeline-comment-header` div                                                                                        |
| E43 | `test_box_header_with_filename`    | path to named file                   | `.Box-header` with `<h2>` containing filename                                                                            |
| E44 | `test_box_header_without_filename` | TextReader, no filename              | No `.Box-header` div                                                                                                     |
| E45 | `test_octicons_stylesheet`         | defaults                             | `octicons.css` link present                                                                                              |
| E46 | `test_favicon_link`                | defaults                             | `<link rel="icon"` present                                                                                               |

### Dimension 4: Correlated — mermaid x page config

Mermaid rendering interacts with some page config options. Sample the
combinations that could plausibly cause bugs.

| ID  | Test                           | Config                              | Assertions                                         |
|-----|--------------------------------|-------------------------------------|----------------------------------------------------|
| E50 | `test_mermaid_dark_theme`      | mermaid block + `theme='dark'`      | SVG present, `data-color-mode=dark`                |
| E51 | `test_mermaid_user_content`    | mermaid block + `user_content=True` | SVG inside `td.comment-body`, not inside `article` |
| E52 | `test_mermaid_with_title`      | mermaid block + `title="Diagrams"`  | Title in `<title>`, SVG in content                 |
| E53 | `test_mermaid_autorefresh_off` | mermaid block + `autorefresh=False` | SVG present, no autorefresh URL                    |

### Dimension 5: Routing and file serving

Tests using `DirectoryReader` to verify path handling, redirects, 404s,
and binary file serving.

| ID  | Test                            | Request                                           | Assertions                                           |
|-----|---------------------------------|---------------------------------------------------|------------------------------------------------------|
| E60 | `test_root_serves_readme`       | `GET /` on dir with README.md                     | 200, content from README.md                          |
| E61 | `test_explicit_file_path`       | `GET /other.md` where other.md exists             | 200, content from other.md                           |
| E62 | `test_missing_file_404`         | `GET /nonexistent.md`                             | 404                                                  |
| E63 | `test_directory_redirect`       | `GET /subdir` where subdir/ exists with README.md | 302 redirect to `/subdir/`                           |
| E64 | `test_directory_serves_readme`  | `GET /subdir/` with README.md inside              | 200, content from subdir README                      |
| E65 | `test_binary_file_served_raw`   | `GET /image.png` where image.png exists           | 200, response is binary, content-type is `image/png` |
| E66 | `test_path_traversal_blocked`   | `GET /../etc/passwd`                              | 404 (werkzeug NotFound)                              |
| E67 | `test_normalized_path_redirect` | `GET /./README.md/`                               | 302 redirect to normalized path                      |

### Dimension 6: Inline rendering and export path

Tests the `render_inline=True` path which inlines styles and favicon.

| ID  | Test                             | Config                               | Assertions                                                          |
|-----|----------------------------------|--------------------------------------|---------------------------------------------------------------------|
| E70 | `test_render_inline_favicon`     | `render_inline=True`                 | `<link rel="icon" href="data:image/x-icon;base64,`                  |
| E71 | `test_render_not_inline_favicon` | `render_inline=False`                | `<link rel="icon" href="` pointing to static URL, not data:         |
| E72 | `test_export_produces_html`      | `grip.export()` with tmp output file | File written, contains `<!DOCTYPE html>`, contains rendered content |
| E73 | `test_export_inline_default`     | `grip.export()` default              | Styles are inlined (no external `<link>` stylesheet URLs)           |
| E74 | `test_export_no_inline`          | `grip.export(render_inline=False)`   | External `<link>` stylesheet URLs present                           |

### Dimension 7: Autorefresh SSE

Test the Server-Sent Events endpoint for content refresh.

| ID  | Test                             | Setup               | Assertions                                                                |
|-----|----------------------------------|---------------------|---------------------------------------------------------------------------|
| E80 | `test_refresh_endpoint_exists`   | `autorefresh=True`  | `GET /__/grip/refresh/` returns 200 with `text/event-stream` content type |
| E81 | `test_refresh_endpoint_disabled` | `autorefresh=False` | `GET /__/grip/refresh/` returns 404                                       |
|     |                                  |                     |                                                                           |

### Dimension 8: Error handling in render pipeline

| ID  | Test                     | Setup                    | Assertions                                                 |
|-----|--------------------------|--------------------------|------------------------------------------------------------|
| E90 | `test_render_empty_file` | Empty markdown file      | 200, empty `#grip-content`                                 |
| E91 | `test_large_markdown`    | 10,000 lines of markdown | 200, response contains rendered content (no timeout/crash) |

---

## Component Tests — `test_mermaid.py`

Unit tests for `GripperRenderer` internals. These test the extraction
regex, placeholder substitution, mmdc integration, and fallback behavior
independently.

### Mermaid block extraction (regex)

Tests the `MERMAID_BLOCK_RE` regex and the extraction phase of `render()`.
These call `render()` with mmdc mocked to return a fixed SVG string, so
they focus on extraction correctness.

| ID  | Test                                 | Input markdown                         | Assertions                                              |
|-----|--------------------------------------|----------------------------------------|---------------------------------------------------------|
| M1  | `test_extract_single_block`          | ` ```mermaid\ngraph LR\n  A-->B\n``` ` | Exactly 1 mmdc call, source is `graph LR\n  A-->B\n`    |
| M2  | `test_extract_multiple_blocks`       | Two mermaid blocks                     | Exactly 2 mmdc calls with correct sources               |
| M3  | `test_extract_no_blocks`             | `# Just a heading`                     | Zero mmdc calls                                         |
| M4  | `test_extract_four_backticks`        | ` ````mermaid\ncontent\n```` `         | 1 call, source is `content\n`                           |
| M5  | `test_non_mermaid_fenced_block`      | ` ```python\nprint(1)\n``` `           | Zero mmdc calls                                         |
| M6  | `test_mermaid_case_sensitive`        | ` ```Mermaid\ncontent\n``` `           | Zero mmdc calls (tag is case-sensitive)                 |
| M7  | `test_empty_mermaid_block`           | ` ```mermaid\n``` `                    | 1 mmdc call with empty string source                    |
| M8  | `test_mermaid_with_trailing_spaces`  | ` ```mermaid   \ncontent\n``` `        | 1 call (regex allows `\s*` after tag)                   |
| M9  | `test_mermaid_block_with_html_chars` | Mermaid source containing `<` and `&`  | Source passed to mmdc verbatim (not escaped)            |
| M10 | `test_mixed_content_ordering`        | Text, mermaid1, text, mermaid2, text   | Output preserves order: `<p>`, SVG1, `<p>`, SVG2, `<p>` |

### Placeholder substitution

Tests the post-rendering substitution phase. Uses a mock `OfflineRenderer`
that returns controlled HTML to test both `<p>`-wrapped and bare
placeholder handling.

| ID  | Test                               | Mock HTML output               | Assertions                                      |
|-----|------------------------------------|--------------------------------|-------------------------------------------------|
| M20 | `test_placeholder_in_p_tags`       | `<p>GRIPPER_MERMAID_0</p>`     | Replaced with SVG div, no `<p>` wrapper remains |
| M21 | `test_placeholder_bare`            | `<div>GRIPPER_MERMAID_0</div>` | Replaced within the div                         |
| M22 | `test_placeholder_with_whitespace` | `<p> GRIPPER_MERMAID_0 </p>`   | Regex handles `\s*`, replaced correctly         |
| M23 | `test_multiple_placeholders`       | Two placeholders in HTML       | Both replaced with correct SVGs (0 and 1 match) |

### mmdc integration

Tests `_render_mermaid()` with the real `mmdc` binary.

| ID  | Test                           | Input                           | Assertions                                                                |
|-----|--------------------------------|---------------------------------|---------------------------------------------------------------------------|
| M30 | `test_mmdc_produces_svg`       | `graph LR\n  A-->B`             | Return value starts with `<div class="mermaid-diagram">`, contains `<svg` |
| M31 | `test_mmdc_svg_is_valid`       | `graph LR\n  A-->B`             | SVG contains `viewBox`, is well-formed XML                                |
| M32 | `test_mmdc_sequence_diagram`   | `sequenceDiagram\n  A->>B: msg` | Contains `<svg`                                                           |
| M33 | `test_mmdc_pie_chart`          | `pie\n  "A": 50\n  "B": 50`     | Contains `<svg`                                                           |
| M34 | `test_mmdc_temp_files_cleaned` | Any valid input                 | After call, no `.mmd` or `.svg` temp files left in tempdir                |

### mmdc failure and fallback

Tests error paths when mmdc is unavailable or fails.

| ID  | Test                                  | Setup                                              | Assertions                                              |
|-----|---------------------------------------|----------------------------------------------------|---------------------------------------------------------|
| M40 | `test_mmdc_not_found`                 | Mock subprocess.run to raise FileNotFoundError     | Returns `<pre><code class="language-mermaid">` fallback |
| M41 | `test_mmdc_nonzero_exit`              | Mock subprocess.run to return returncode=1         | Returns fallback code block                             |
| M42 | `test_mmdc_timeout`                   | Mock subprocess.run to raise TimeoutExpired        | Returns fallback code block                             |
| M43 | `test_fallback_escapes_html`          | Mermaid source `A --> B<script>` with mmdc failing | Fallback output contains `&lt;script&gt;` (escaped)     |
| M44 | `test_fallback_preserves_content`     | Mermaid source with special chars, mmdc failing    | Source text appears in fallback `<code>` block          |
| M45 | `test_render_continues_after_failure` | Two blocks, first mmdc call fails, second succeeds | First block is fallback, second is SVG                  |
| M46 | `test_temp_files_cleaned_on_failure`  | mmdc fails                                         | No temp files left behind                               |

### OfflineRenderer base rendering

Tests that the base `OfflineRenderer.render()` works correctly (it was
previously untested and had bugs).

| ID  | Test                              | Input                      | Assertions                             |
|-----|-----------------------------------|----------------------------|----------------------------------------|
| M50 | `test_offline_render_basic`       | `**bold**`                 | Returns `<p><strong>bold</strong></p>` |
| M51 | `test_offline_render_fenced_code` | ` ```python\nx=1\n``` `    | Returns `<code` block                  |
| M52 | `test_offline_render_table`       | GFM table                  | Returns `<table>` with rows            |
| M53 | `test_offline_render_toc_ids`     | `# Heading`                | `<h1 id="heading">`                    |
| M54 | `test_offline_render_urlize`      | `Visit http://example.com` | `<a href="http://example.com">`        |
| M55 | `test_offline_render_codehilite`  | Fenced code with language  | `class="highlight"` in output          |
| M56 | `test_offline_render_empty`       | `""`                       | Returns `""` (empty string)            |

---

## Test infrastructure

### Fixtures (conftest.py additions)

```python
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
```

### Mocking mmdc for component tests

For regex/placeholder tests that need to isolate extraction from
rendering, mock `subprocess.run` to return a canned SVG:

```python
MOCK_SVG = '<svg xmlns="http://www.w3.org/2000/svg"><text>mock</text></svg>'

@pytest.fixture
def mock_mmdc(monkeypatch):
    """Patches subprocess.run so mmdc returns a fixed SVG."""
    call_args = []
    def fake_run(cmd, **kwargs):
        call_args.append(cmd)
        # Write mock SVG to the -o output path
        out_path = cmd[cmd.index('-o') + 1]
        with open(out_path, 'w') as f:
            f.write(MOCK_SVG)
        return subprocess.CompletedProcess(cmd, 0, '', '')
    monkeypatch.setattr('subprocess.run', fake_run)
    return call_args
```

### Marking slow tests

Tests that invoke real `mmdc` (M30-M34) are slower (~2-5s each).
Mark them with `@pytest.mark.slow` and add to pytest.ini:

```ini
markers =
    assumption: external assumption test
    slow: tests that invoke mmdc (mermaid-cli)
```

---

## Files

| File                    | Purpose                    |
|-------------------------|----------------------------|
| `tests/test_e2e.py`     | E2E tests (E1-E91)         |
| `tests/test_mermaid.py` | Component tests (M1-M56)   |
| `tests/conftest.py`     | Updated with new fixtures  |
| `pytest.ini`            | Updated with `slow` marker |

## Running

```console
# All new tests
pytest tests/test_e2e.py tests/test_mermaid.py -v

# Skip slow mmdc tests
pytest tests/test_e2e.py tests/test_mermaid.py -v -m "not slow"

# Only mermaid component tests
pytest tests/test_mermaid.py -v

# With coverage
pytest tests/test_e2e.py tests/test_mermaid.py --cov=grip --cov-report=term-missing
```
