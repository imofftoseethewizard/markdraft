# Test Plan

## Approach

Tests are organized into four files by component:

1. **`test_server.py`** — E2E tests via HTTP requests to a live
   `PreviewServer`. Primary test surface.
2. **`test_export.py`** — Tests for HTML export (inline and CDN-linked).
3. **`test_cli.py`** — Tests for CLI argument parsing and `main()`.
4. **`test_components.py`** — Unit tests for readers, asset cache, file
   watcher, browser helpers, config loading, address parsing, and
   exceptions.

### Coverage target

Line coverage of all Python code in `markdraft/`, excepting catch-all
exception handlers (`except Exception: pass`). JavaScript is not tested
from Python — rendering correctness is delegated to marked.js,
highlight.js, and mermaid.js.

### Semantic dimensions

The input space decomposes into orthogonal dimensions. Each dimension is
sampled across its equivalence classes. Correlated dimensions that
interact are tested combinatorially; independent dimensions are tested
in isolation.

---

## Cleanup

Delete legacy test artifacts from the grip era:

| Path | Reason |
|------|--------|
| `tests/output/` | Unused — saved HTML from old GitHub API renderer |
| `tests/input/github.md` | Duplicate of gfm-test.md |
| `tests/input/simple.md` | Only used by deleted GitHubRenderer tests |
| `tests/input/zero.md` | Only used by deleted GitHubRenderer tests |
| `tests/helpers.py` | Imported by nobody |
| `tests/mermaid_test.md` | From the mmdc era, no tests reference it |
| `tests/PLAN.md` | Replaced by this file |

Keep:

| Path | Reason |
|------|--------|
| `tests/input/default/README.md` | Used by DirectoryReader tests |
| `tests/input/gfm-test.md` | Used by DirectoryReader tests |
| `tests/input/img.png` | Used by is_binary() test |

Create `tests/input/empty/` as an empty directory (for ReadmeNotFoundError
tests — currently relies on the directory existing).

---

## E2E Server Tests — `test_server.py`

Each test starts a `PreviewServer` on a random port using the
`preview_server` / `text_server` / `dir_server` fixtures from conftest,
then makes HTTP requests with `urllib.request`.

### Dimension 1: Page serving (HTML shell)

The server serves an HTML shell for markdown files. The browser fetches
raw markdown from the API and renders it client-side.

| ID | Test | Input | Assertions |
|----|------|-------|------------|
| S1 | `test_root_serves_html_shell` | TextReader with markdown | 200, `<!DOCTYPE html>`, `markdraft-content` |
| S2 | `test_page_has_data_attributes` | TextReader | `data-content-url`, `data-color-mode` present |
| S3 | `test_page_includes_script_tags` | TextReader | `marked.min.js`, `highlight.min.js`, `mermaid.min.js`, `markdraft.js` |
| S4 | `test_page_includes_css_links` | TextReader | `github-markdown.css`, `markdraft.css`, `octicons.css` |

### Dimension 2: Page title

| ID | Test | Config | Assertion |
|----|------|--------|-----------|
| S5 | `test_title_from_filename` | display_filename='README.md' | `README.md - Markdraft` in `<title>` |
| S6 | `test_title_override` | title='Custom' | `Custom` in `<title>` |
| S7 | `test_title_no_filename` | display_filename=None | `Markdraft` in `<title>` |

### Dimension 3: Theme (orthogonal)

| ID | Test | Config | Assertion |
|----|------|--------|-----------|
| S8 | `test_theme_light` | theme='light' | `data-color-mode="light"`, light highlight CSS |
| S9 | `test_theme_dark` | theme='dark' | `data-color-mode="dark"`, dark highlight CSS |

### Dimension 4: Layout (orthogonal)

| ID | Test | Config | Assertion |
|----|------|--------|-----------|
| S10 | `test_readme_layout` | default | `id="readme"` present, no `pull-discussion-timeline` |
| S11 | `test_user_content_layout` | user_content=True | `pull-discussion-timeline` present, no `id="readme"` |
| S12 | `test_user_content_with_title` | user_content=True, title='Issue' | `timeline-comment-header` with title |
| S13 | `test_user_content_without_title` | user_content=True, no title, no filename | No `timeline-comment-header` |

### Dimension 5: Autorefresh

| ID | Test | Config | Assertion |
|----|------|--------|-----------|
| S14 | `test_autorefresh_url_present` | autorefresh=True | `data-refresh-url` contains `/api/refresh` |
| S15 | `test_autorefresh_url_empty` | autorefresh=False | `data-refresh-url=""` |

### Dimension 6: JSON content API

| ID | Test | Input | Assertion |
|----|------|-------|-----------|
| S16 | `test_api_returns_json` | TextReader('# Hello') | 200, Content-Type: application/json |
| S17 | `test_api_returns_raw_markdown` | TextReader('# Hello\n\n**bold**') | `{"text": "# Hello\n\n**bold**", ...}` |
| S18 | `test_api_returns_filename` | display_filename='README.md' | `{"filename": "README.md"}` |
| S19 | `test_api_subpath` | DirReader with other.md | `/__/api/content/other.md` returns its text |
| S20 | `test_api_missing_file` | TextReader | 404 for `/__/api/content/nonexistent.md` |

### Dimension 7: SSE refresh endpoint

| ID | Test | Config | Assertion |
|----|------|--------|-----------|
| S21 | `test_refresh_enabled_in_html` | autorefresh=True | Page HTML has non-empty refresh URL |
| S22 | `test_refresh_disabled_returns_404` | autorefresh=False | 404 on `/__/api/refresh` |

### Dimension 8: Static file serving

| ID | Test | Request | Assertion |
|----|------|---------|-----------|
| S23 | `test_serve_bundled_css` | `/__/static/markdraft.css` | 200, `.preview-page` in body |
| S24 | `test_serve_bundled_js` | `/__/static/markdraft.js` | 200, `marked` in body |
| S25 | `test_serve_favicon` | `/__/static/favicon.ico` | 200 |
| S26 | `test_serve_cached_asset` | Place file in cache, request it | 200, correct content |
| S27 | `test_missing_static_404` | `/__/static/nonexistent.xyz` | 404 |
| S28 | `test_static_path_traversal` | `/__/static/../../../etc/passwd` | 404 |
| S29 | `test_static_empty_filename` | `/__/static/` | 404 |

### Dimension 9: Directory routing (correlated with reader)

| ID | Test | Files | Request | Assertion |
|----|------|-------|---------|-----------|
| S30 | `test_root_serves_readme` | README.md | `GET /` | 200, HTML shell |
| S31 | `test_explicit_file` | README.md, other.md | `GET /other.md` | 200 |
| S32 | `test_missing_file_404` | README.md | `GET /nonexistent.md` | 404 |
| S33 | `test_subdirectory_serves_readme` | sub/README.md | `GET /sub/` | 200 |
| S34 | `test_binary_file_raw` | README.md, image.png | `GET /image.png` | 200, `image/png`, PNG bytes |
| S35 | `test_path_traversal_blocked` | README.md | `GET /../../../etc/passwd` | 404 |
| S36 | `test_normalized_redirect` | README.md | `GET /sub` (dir exists) | 302 to `/sub/` |

### Dimension 10: Quiet mode

| ID | Test | Config | Assertion |
|----|------|--------|-----------|
| S37 | `test_quiet_suppresses_log` | quiet=True | No stderr output from handler |

---

## Export Tests — `test_export.py`

Tests for `export_page()` which produces self-contained HTML.

### Dimension 1: Inline vs CDN

| ID | Test | Config | Assertion |
|----|------|--------|-----------|
| E1 | `test_inline_contains_css` | inline=True | `<style>` with CSS content |
| E2 | `test_inline_contains_js` | inline=True | `<script>` with JS content |
| E3 | `test_inline_contains_markdraft_js` | inline=True | `marked.parse` in output |
| E4 | `test_no_inline_has_cdn_links` | inline=False | `cdn.jsdelivr.net` in `<script src>` and `<link href>` |

### Dimension 2: Markdown embedding

| ID | Test | Input | Assertion |
|----|------|-------|-----------|
| E5 | `test_markdown_embedded` | `# Hello\n**bold**` | Raw markdown in `markdraft-source` script tag |
| E6 | `test_script_tag_escaped` | `text</script>more` | `<\\/script` in output, no premature close |

### Dimension 3: Page metadata

| ID | Test | Config | Assertion |
|----|------|--------|-----------|
| E7 | `test_title_in_export` | title='My Page' | `<title>My Page</title>` |
| E8 | `test_dark_theme` | theme='dark' | `data-color-mode="dark"`, dark highlight CSS |
| E9 | `test_user_content_layout` | user_content=True | `pull-discussion-timeline`, no `id="readme"` |
| E10 | `test_readme_layout_default` | default | `id="readme"`, no `pull-discussion-timeline` |

### Dimension 4: Output destination

| ID | Test | out_file | Assertion |
|----|------|----------|-----------|
| E11 | `test_export_to_file` | path to file | File written, contains `<!DOCTYPE html>` |
| E12 | `test_export_to_stdout` | `'-'` | Captured stdout contains HTML |
| E13 | `test_export_returns_string` | `None` | Returns HTML string |

---

## CLI Tests — `test_cli.py`

### Subprocess tests

| ID | Test | Command | Assertion |
|----|------|---------|-----------|
| C1 | `test_help` | `draft -h` | Output contains 'draft' |
| C2 | `test_version` | `draft -V` | Output is version string |
| C3 | `test_bad_flag` | `draft --nope` | Non-zero exit |

### Direct main() tests

| ID | Test | argv | Assertion |
|----|------|------|-----------|
| C4 | `test_version_flag` | `['-V']` | Returns 0, prints version |
| C5 | `test_deprecated_a_flag` | `['-a']` | Returns 2 |
| C6 | `test_deprecated_p_flag` | `['-p']` | Returns 2 |
| C7 | `test_theme_invalid` | `['--theme=bad', '--export', '.']` | Returns 1 |
| C8 | `test_theme_light_export` | `['--theme=light', '--export', path, out, '--quiet']` | Returns 0 |
| C9 | `test_theme_dark_export` | `['--theme=dark', '--export', path, out, '--quiet']` | Returns 0 |
| C10 | `test_clear_flag` | `['--clear']` | Returns 0, calls clear_cache |
| C11 | `test_export_writes_file` | `['--export', path, out, '--quiet']` | File created with content |
| C12 | `test_export_with_title` | `['--export', '--title=X', path, out, '--quiet']` | Title in HTML |
| C13 | `test_missing_readme` | `['--export', empty_dir]` | Returns 1, prints 'Error' |
| C14 | `test_quiet_export` | `['--export', '--quiet', path, out]` | No 'Exporting to' on stderr |
| C15 | `test_no_inline_export` | `['--export', '--no-inline', path, out, '--quiet']` | CDN links in HTML |

---

## Component Tests — `test_components.py`

Unit tests for modules with non-trivial logic.

### Readers

| ID | Test | Class | Assertion |
|----|------|-------|-----------|
| R1 | `test_directory_reader_finds_readme` | DirectoryReader | Finds README.md in directory |
| R2 | `test_directory_reader_explicit_file` | DirectoryReader | Accepts explicit .md path |
| R3 | `test_directory_reader_silent_missing` | DirectoryReader(silent=True) | Returns default path |
| R4 | `test_directory_reader_raises_missing` | DirectoryReader | Raises ReadmeNotFoundError |
| R5 | `test_directory_reader_normalize_none` | normalize_subpath(None) | Returns None |
| R6 | `test_directory_reader_normalize_dir` | normalize_subpath('subdir') | Adds trailing `/` |
| R7 | `test_directory_reader_normalize_file` | normalize_subpath('file.md') | No trailing `/` |
| R8 | `test_directory_reader_traversal_blocked` | normalize_subpath('../escape') | Raises ReadmeNotFoundError |
| R9 | `test_directory_reader_is_binary` | is_binary('img.png') | True |
| R10 | `test_directory_reader_is_text` | is_binary('file.md') | False |
| R11 | `test_directory_reader_last_updated` | last_updated for existing file | Returns float |
| R12 | `test_directory_reader_last_updated_missing` | last_updated for missing | Returns None |
| R13 | `test_directory_reader_read_text` | read('file.md') | Returns str |
| R14 | `test_directory_reader_read_binary` | read('img.png') | Returns bytes |
| R15 | `test_directory_reader_read_missing` | read('nope.md') | Raises ReadmeNotFoundError |
| R16 | `test_text_reader_read` | TextReader('text').read() | Returns 'text' |
| R17 | `test_text_reader_subpath_raises` | TextReader('text').read('x') | Raises ReadmeNotFoundError |
| R18 | `test_text_reader_filename` | TextReader('t', 'f.md').filename_for(None) | Returns 'f.md' |
| R19 | `test_stdin_reader_reads_once` | StdinReader mock | Calls read_stdin once |

### Asset cache

| ID | Test | Method | Assertion |
|----|------|--------|-----------|
| A1 | `test_get_path` | get_path('x.js') | Correct join |
| A2 | `test_is_cached_true` | File exists | True |
| A3 | `test_is_cached_false` | File missing | False |
| A4 | `test_all_cached_true` | All CDN files exist | True |
| A5 | `test_all_cached_false` | Some missing | False |
| A6 | `test_ensure_downloads` | Empty cache | Calls urlretrieve N times |
| A7 | `test_ensure_skips_existing` | Full cache | Zero downloads |
| A8 | `test_ensure_handles_failure` | urlretrieve raises | No crash, prints warning |
| A9 | `test_clear_removes_dir` | Populated cache | Dir gone |
| A10 | `test_clear_missing_dir` | No dir | No error |

### File watcher

| ID | Test | Scenario | Assertion |
|----|------|----------|-----------|
| W1 | `test_yields_on_change` | Modify file mtime | Generator yields True |
| W2 | `test_exits_on_shutdown` | Set shutdown_event | Generator returns |
| W3 | `test_no_yield_without_change` | No change, then shutdown | No yields |

### Browser helpers

| ID | Test | Function | Assertion |
|----|------|----------|-----------|
| B1 | `test_is_server_running_true` | Listening socket | Returns True |
| B2 | `test_is_server_running_false` | No listener | Returns False |
| B3 | `test_wait_for_server_cancel` | cancel_event set | Returns False |
| B4 | `test_start_browser_when_ready` | Mock webbrowser | Thread starts, calls open |

### Config loading

| ID | Test | Scenario | Assertion |
|----|------|----------|-----------|
| G1 | `test_load_missing_file` | No settings.py | Returns {} |
| G2 | `test_load_settings` | Write settings.py with HOST='0.0.0.0' | Returns {'HOST': '0.0.0.0'} |
| G3 | `test_load_ignores_lowercase` | Write foo='bar' | Not in result |
| G4 | `test_env_var_override` | Set MARKDRAFT_HOME | Uses that path |
| G5 | `test_resolve_config_defaults` | No args | HOST/PORT/AUTOREFRESH from config module |
| G6 | `test_resolve_config_cli_overrides` | host='0.0.0.0' | Overrides default |
| G7 | `test_resolve_config_settings_override` | Settings file with PORT=9000 | Uses 9000 |

### Address parsing

| ID | Test | Input | Expected |
|----|------|-------|----------|
| P1 | `test_split_none` | None | (None, None) |
| P2 | `test_split_port_only` | '8080' | (None, 8080) |
| P3 | `test_split_host_only` | 'localhost' | ('localhost', None) |
| P4 | `test_split_host_port` | 'localhost:8080' | ('localhost', 8080) |
| P5 | `test_split_empty` | '' | (None, None) |
| P6 | `test_split_host_bad_port` | 'host:abc' | ('host:abc', None) |
| P7 | `test_resolve_none_none` | (None, None) | (None, None) |
| P8 | `test_resolve_path_only` | ('README.md', None) | ('README.md', None) |
| P9 | `test_resolve_port_as_path` | ('8080', None) | (None, '8080') |
| P10 | `test_resolve_both` | ('README.md', '8080') | ('README.md', '8080') |

### Exceptions

| ID | Test | Scenario | Assertion |
|----|------|----------|-----------|
| X1 | `test_str_default` | ReadmeNotFoundError() | 'README not found' |
| X2 | `test_str_with_path` | ReadmeNotFoundError('.') | 'No README found at .' |
| X3 | `test_str_with_message` | ReadmeNotFoundError('p', 'msg') | 'msg' |
| X4 | `test_filename_attribute` | ReadmeNotFoundError('f.md') | .filename == 'f.md' |
| X5 | `test_repr` | ReadmeNotFoundError('p', 'm') | Contains class name |

---

## API Integration Tests — in `test_cli.py`

These exercise the `export()` and `clear_cache()` API functions
end-to-end (they're thin wrappers, so CLI tests cover them).

| ID | Test | Function | Assertion |
|----|------|----------|-----------|
| I1 | `test_export_default_filename` | export(path) with no out_filename | Creates `README.html` |
| I2 | `test_export_stdout` | export(path, out_filename='-') | Prints to stdout |
| I3 | `test_clear_cache` | clear_cache() | No error |

---

## Test infrastructure

### Fixtures (`conftest.py`)

```
preview_server(tmp_path) → factory(reader, **config) → TestClient
text_server(tmp_path) → factory(text, **kwargs) → TestClient
dir_server(tmp_path) → factory(files_dict, **kwargs) → TestClient
```

`TestClient` wraps `urllib.request` with `.get(path)` returning a
`Response` with `.status_code`, `.data`, `.text()`, `.json()`,
`.headers`.

`MockAssetCache` subclasses `AssetCache` — creates the cache dir but
skips downloads.

### Test input files

```
tests/input/
  default/README.md    — directory reader tests
  gfm-test.md          — large markdown file
  empty/               — empty directory (no README)
  img.png              — binary file detection
```

### Running

```console
uv run pytest tests/ -v                      # all tests
uv run pytest tests/test_server.py -v        # server only
uv run pytest tests/test_components.py -v    # unit tests only
uv run pyright markdraft/                    # type check
```
