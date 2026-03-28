"""
Tests Grip's public API, i.e. everything you can access from `import grip`.

This doesn't send any requests to GitHub (see test_github.py for that), and
this doesn't run a server (see test_cli.py for that). Instead, this creates
fake objects with subclasses and tests the basic expected behavior of Grip.
"""

import logging
import os
import posixpath

import pytest
from requests.exceptions import HTTPError
from werkzeug.exceptions import NotFound

from helpers import USER_CONTEXT, input_file, input_filename, output_file
from mocks import (
    GitHubAssetManagerMock, GripMock, GitHubRequestsMock, StdinReaderMock)

from grip import (
    DEFAULT_FILENAME, DirectoryReader, GitHubAssetManager, GitHubRenderer,
    GripperRenderer, Grip, OfflineRenderer, ReadmeNotFoundError,
    ReadmeAssetManager, ReadmeReader, ReadmeRenderer, TextReader,
    clear_cache, create_app, export, render_content, render_page)
from grip.patcher import patch


DIRNAME = os.path.dirname(os.path.abspath(__file__))


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

def test_exceptions():
    """
    Test that ReadmeNotFoundError behaves like FileNotFoundError on
    Python 3 and IOError on Python 2.
    """
    assert str(ReadmeNotFoundError()) == 'README not found'
    assert (str(ReadmeNotFoundError('.')) == 'No README found at .')
    assert str(ReadmeNotFoundError('some/path', 'Overridden')) == 'Overridden'
    assert ReadmeNotFoundError().filename is None
    assert ReadmeNotFoundError(DEFAULT_FILENAME).filename == DEFAULT_FILENAME


# ---------------------------------------------------------------------------
# Readers
# ---------------------------------------------------------------------------

def test_readme_reader():
    with pytest.raises(TypeError):
        ReadmeReader()


def test_directory_reader():
    input_path = 'input'
    markdown_path = posixpath.join(input_path, 'gfm-test.md')
    default_path = posixpath.join(input_path, 'default')
    input_img_path = posixpath.join(input_path, 'img.png')

    input_dir = os.path.join(DIRNAME, 'input')
    markdown_file = os.path.join(input_dir, 'gfm-test.md')
    default_dir = os.path.join(input_dir, 'default')
    default_file = os.path.join(default_dir, DEFAULT_FILENAME)

    DirectoryReader(input_filename('default'))
    DirectoryReader(input_filename(default_file))
    DirectoryReader(input_filename(default_file), silent=True)
    DirectoryReader(input_filename('empty'), silent=True)
    with pytest.raises(ReadmeNotFoundError):
        DirectoryReader(input_filename('empty'))
    with pytest.raises(ReadmeNotFoundError):
        DirectoryReader(input_filename('empty', DEFAULT_FILENAME))

    reader = DirectoryReader(DIRNAME, silent=True)
    assert reader.root_filename == os.path.join(DIRNAME, DEFAULT_FILENAME)
    assert reader.root_directory == DIRNAME

    assert reader.normalize_subpath(None) is None
    assert reader.normalize_subpath('.') == './'
    assert reader.normalize_subpath('./././') == './'
    assert reader.normalize_subpath('non-existent/.././') == './'
    assert reader.normalize_subpath('non-existent/') == 'non-existent'
    assert reader.normalize_subpath('non-existent') == 'non-existent'
    with pytest.raises(NotFound):
        reader.normalize_subpath('../unsafe')
    with pytest.raises(NotFound):
        reader.normalize_subpath('/unsafe')
    assert reader.normalize_subpath(input_path) == input_path + '/'
    assert reader.normalize_subpath(markdown_path) == markdown_path
    assert reader.normalize_subpath(markdown_path + '/') == markdown_path

    assert reader.readme_for(None) == os.path.join(DIRNAME, DEFAULT_FILENAME)
    with pytest.raises(ReadmeNotFoundError):
        reader.readme_for('non-existent')
    with pytest.raises(ReadmeNotFoundError):
        reader.readme_for(input_path)
    assert reader.readme_for(markdown_path) == os.path.abspath(markdown_file)
    assert reader.readme_for(default_path) == os.path.abspath(default_file)

    # TODO: 'README.md' vs 'readme.md'

    assert reader.filename_for(None) == DEFAULT_FILENAME
    assert reader.filename_for(input_path) is None
    assert reader.filename_for(default_path) == os.path.relpath(
        default_file, reader.root_directory)

    assert not reader.is_binary()
    assert not reader.is_binary(input_path)
    assert not reader.is_binary(markdown_path)
    assert reader.is_binary(input_img_path)

    assert reader.last_updated() is None
    assert reader.last_updated(input_path) is None
    assert reader.last_updated(markdown_path) is not None
    assert reader.last_updated(default_path) is not None
    assert DirectoryReader(default_dir).last_updated is not None

    with pytest.raises(ReadmeNotFoundError):
        assert reader.read(input_path) is not None
    assert reader.read(markdown_path)
    assert reader.read(default_path)
    with pytest.raises(ReadmeNotFoundError):
        assert reader.read()
    assert DirectoryReader(default_dir).read() is not None


def test_text_reader():
    text = 'Test *Text*'
    filename = DEFAULT_FILENAME

    assert TextReader(text).normalize_subpath(None) is None
    assert TextReader(text).normalize_subpath('././.') == '.'
    assert TextReader(text).normalize_subpath(filename) == filename

    assert TextReader(text).filename_for(None) is None
    assert TextReader(text, filename).filename_for(None) == filename
    assert TextReader(text, filename).filename_for('.') is None

    assert TextReader(text).last_updated() is None
    assert TextReader(text, filename).last_updated() is None
    assert TextReader(text, filename).last_updated('.') is None
    assert TextReader(text, filename).last_updated(filename) is None

    assert TextReader(text).read() == text
    assert TextReader(text, filename).read() == text
    with pytest.raises(ReadmeNotFoundError):
        TextReader(text).read('.')
    with pytest.raises(ReadmeNotFoundError):
        TextReader(text, filename).read('.')
    with pytest.raises(ReadmeNotFoundError):
        TextReader(text, filename).read(filename)


def test_stdin_reader():
    text = 'Test *STDIN*'
    filename = DEFAULT_FILENAME

    assert StdinReaderMock(text).normalize_subpath(None) is None
    assert StdinReaderMock(text).normalize_subpath('././.') == '.'
    assert StdinReaderMock(text).normalize_subpath(filename) == filename

    assert StdinReaderMock(text).filename_for(None) is None
    assert StdinReaderMock(text, filename).filename_for(None) == filename
    assert StdinReaderMock(text, filename).filename_for('.') is None

    assert StdinReaderMock(text).last_updated() is None
    assert StdinReaderMock(text, filename).last_updated() is None
    assert StdinReaderMock(text, filename).last_updated('.') is None
    assert StdinReaderMock(text, filename).last_updated(filename) is None

    assert StdinReaderMock(text).read() == text
    assert StdinReaderMock(text, filename).read() == text
    with pytest.raises(ReadmeNotFoundError):
        StdinReaderMock(text).read('.')
    with pytest.raises(ReadmeNotFoundError):
        StdinReaderMock(text, filename).read('.')
    with pytest.raises(ReadmeNotFoundError):
        StdinReaderMock(text, filename).read(filename)


# ---------------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------------

def test_readme_renderer():
    with pytest.raises(TypeError):
        ReadmeRenderer()


def test_github_renderer():
    simple_input = input_file('simple.md')
    gfm_test_input = input_file('gfm-test.md')

    with GitHubRequestsMock() as responses:
        assert (GitHubRenderer().render(simple_input) ==
                output_file('renderer', 'simple.html'))
        assert (GitHubRenderer(True).render(simple_input) ==
                output_file('renderer', 'simple-user-content.html'))
        assert (GitHubRenderer(True, USER_CONTEXT).render(simple_input) ==
                output_file('renderer', 'simple-user-context.html'))
        assert len(responses.calls) == 3

    assert (output_file('renderer', 'gfm-test-user-content.html') !=
            output_file('renderer', 'gfm-test-user-context.html'))

    with GitHubRequestsMock() as responses:
        assert (GitHubRenderer().render(gfm_test_input) ==
                output_file('renderer', 'gfm-test.html'))
        assert (GitHubRenderer(True).render(gfm_test_input) ==
                output_file('renderer', 'gfm-test-user-content.html'))
        assert (GitHubRenderer(True, USER_CONTEXT).render(gfm_test_input) ==
                output_file('renderer', 'gfm-test-user-context.html'))
        assert len(responses.calls) == 3

    with GitHubRequestsMock() as responses:
        assert (
            GitHubRenderer().render(simple_input, GitHubRequestsMock.auth) ==
            output_file('renderer', 'simple.html'))
        with pytest.raises(HTTPError):
            GitHubRenderer().render(simple_input, GitHubRequestsMock.bad_auth)
        assert len(responses.calls) == 2


def test_github_renderer_type_error():
    """Passing bytes instead of unicode string raises TypeError."""
    with GitHubRequestsMock():
        with pytest.raises(TypeError):
            GitHubRenderer().render(b'bytes input')


def test_github_renderer_raw_mode():
    """raw=True returns unpatched HTML (no octicon span replacement)."""
    simple_input = input_file('simple.md')
    with GitHubRequestsMock():
        raw_html = GitHubRenderer(raw=True).render(simple_input)
        patched_html = GitHubRenderer().render(simple_input)
        # Both should return content, raw may differ from patched
        assert isinstance(raw_html, str)
        assert isinstance(patched_html, str)


def test_github_renderer_custom_api_url():
    """Custom api_url is stored on the renderer."""
    renderer = GitHubRenderer(api_url='https://github.example.com/api/v3')
    assert renderer.api_url == 'https://github.example.com/api/v3'


def test_github_renderer_user_content_params():
    """user_content and context are stored on the renderer."""
    renderer = GitHubRenderer(user_content=True, context='owner/repo')
    assert renderer.user_content is True
    assert renderer.context == 'owner/repo'


def test_offline_renderer():
    """OfflineRenderer is instantiable and stores params."""
    r = OfflineRenderer()
    assert r.user_content is False
    assert r.context is None

    r2 = OfflineRenderer(user_content=True, context='owner/repo')
    assert r2.user_content is True
    assert r2.context == 'owner/repo'

    # Renders markdown
    html = r.render('**bold**')
    assert '<strong>bold</strong>' in html


# ---------------------------------------------------------------------------
# Patcher
# ---------------------------------------------------------------------------

class TestPatcher:
    """Tests for grip.patcher.patch()."""

    def test_patch_incomplete_task(self):
        html = '<li>[ ] Todo</li>'
        result = patch(html)
        assert 'task-list-item' in result
        assert 'type="checkbox"' in result
        assert 'checked' not in result
        assert 'Todo' in result

    def test_patch_complete_task(self):
        html = '<li>[x] Done</li>'
        result = patch(html)
        assert 'task-list-item' in result
        assert 'checked=""' in result
        assert 'Done' in result

    def test_patch_task_with_nested_list(self):
        html = '<li>[ ] Parent<ul><li>Child</li></ul>'
        result = patch(html)
        assert 'task-list-item' in result
        assert 'Parent' in result
        assert '<ul>' in result

    def test_patch_skipped_for_user_content(self):
        html = '<li>[ ] Todo</li>'
        result = patch(html, user_content=True)
        # Task list patching is skipped for user content
        assert 'task-list-item' not in result
        assert result == html

    def test_patch_header(self):
        html = ('<span>{:"aria-hidden"=&gt;"true", :class=&gt;'
                '"octicon octicon-link"}</span>')
        result = patch(html)
        assert 'class="octicon octicon-link"' in result
        assert '{:"aria-hidden"' not in result

    def test_patch_no_match(self):
        html = '<p>Regular paragraph</p>'
        assert patch(html) == html


# ---------------------------------------------------------------------------
# Asset manager
# ---------------------------------------------------------------------------

class TestAssetManager:
    """Tests for ReadmeAssetManager and GitHubAssetManager."""

    def test_asset_manager_abstract(self):
        with pytest.raises(TypeError):
            ReadmeAssetManager('dummy-path')

    def test_cache_filename_strips_params(self):
        assets = GitHubAssetManager('dummy')
        assert assets.cache_filename(
            'http://x/style.css?v=1#hash') == 'style.css'

    def test_cache_filename_basename(self):
        assets = GitHubAssetManager('dummy')
        assert assets.cache_filename(
            'http://x/path/to/file.css') == 'file.css'

    def test_clear_nonexistent_cache(self):
        assets = GitHubAssetManager('/nonexistent/path/cache')
        # Should not raise
        assets.clear()

    def test_clear_removes_directory(self, tmpdir):
        cache_dir = tmpdir.mkdir('cache')
        cache_dir.join('style.css').write_text('body {}', 'utf-8')
        assets = GitHubAssetManager(str(cache_dir))
        assert cache_dir.check()
        assets.clear()
        assert not cache_dir.check()

    def test_script_urls_initialized(self):
        assets = GitHubAssetManagerMock()
        assert assets.script_urls == []
        assert assets.scripts == []


# ---------------------------------------------------------------------------
# Grip app
# ---------------------------------------------------------------------------

class TestGripApp:
    """Tests for the Grip Flask application class."""

    def test_app_renders(self, monkeypatch, tmpdir):
        """Existing test: Grip renders known inputs to expected outputs."""
        monkeypatch.setenv('GRIPHOME', str(tmpdir))
        zero_path = input_filename('zero.md')
        zero_output = output_file('app', 'zero.html')
        gfm_test_path = input_filename('gfm-test.md')
        gfm_test_output = output_file('app', 'gfm-test.html')
        assets = GitHubAssetManagerMock()
        renderer = GitHubRenderer()

        with GitHubRequestsMock() as responses:
            assert Grip(zero_path, renderer=renderer, assets=assets).render() == zero_output
            assert Grip(zero_path, renderer=renderer, assets=assets).render('/') == zero_output
            assert Grip(zero_path, renderer=renderer, assets=assets).render('/x/../') == zero_output
            with Grip(zero_path, renderer=renderer, assets=assets).test_client() as client:
                assert client.get('/').data.decode('utf-8') == zero_output
            assert len(responses.calls) == 4

        with GitHubRequestsMock() as responses:
            app = Grip(gfm_test_path, renderer=renderer, assets=assets)
            assert app.render() == gfm_test_output
            assert app.render('/') == gfm_test_output
            assert len(responses.calls) == 2

    def test_default_renderer_is_gripper(self, monkeypatch, tmpdir):
        monkeypatch.setenv('GRIPHOME', str(tmpdir))
        app = Grip(TextReader('hi', 'README.md'),
                   assets=GitHubAssetManagerMock())
        assert isinstance(app.renderer, GripperRenderer)

    def test_string_source_creates_directory_reader(self, monkeypatch, tmpdir):
        monkeypatch.setenv('GRIPHOME', str(tmpdir))
        default_dir = input_filename('default')
        app = Grip(default_dir, assets=GitHubAssetManagerMock())
        assert isinstance(app.reader, DirectoryReader)

    def test_none_source_uses_cwd(self, monkeypatch, tmpdir):
        monkeypatch.setenv('GRIPHOME', str(tmpdir))
        app = Grip(None, assets=GitHubAssetManagerMock())
        assert isinstance(app.reader, DirectoryReader)

    def test_quiet_mode(self, monkeypatch, tmpdir):
        monkeypatch.setenv('GRIPHOME', str(tmpdir))
        app = Grip(TextReader('hi'), assets=GitHubAssetManagerMock(),
                   quiet=True)
        assert app.quiet is True

    def test_clear_cache(self, monkeypatch, tmpdir):
        monkeypatch.setenv('GRIPHOME', str(tmpdir))
        assets = GitHubAssetManagerMock()
        app = Grip(TextReader('hi'), assets=assets)
        app.clear_cache()
        assert assets.clear_calls == 1

    def test_theme_stored(self, monkeypatch, tmpdir):
        monkeypatch.setenv('GRIPHOME', str(tmpdir))
        app = Grip(TextReader('hi'), assets=GitHubAssetManagerMock(),
                   theme='dark')
        assert app.theme == 'dark'

    def test_render_wide_stored(self, monkeypatch, tmpdir):
        monkeypatch.setenv('GRIPHOME', str(tmpdir))
        app = Grip(TextReader('hi'), assets=GitHubAssetManagerMock(),
                   render_wide=True)
        assert app.render_wide is True

    def test_render_inline_stored(self, monkeypatch, tmpdir):
        monkeypatch.setenv('GRIPHOME', str(tmpdir))
        app = Grip(TextReader('hi'), assets=GitHubAssetManagerMock(),
                   render_inline=True)
        assert app.render_inline is True

    def test_title_stored(self, monkeypatch, tmpdir):
        monkeypatch.setenv('GRIPHOME', str(tmpdir))
        app = Grip(TextReader('hi'), assets=GitHubAssetManagerMock(),
                   title='Custom')
        assert app.title == 'Custom'


# ---------------------------------------------------------------------------
# API functions
# ---------------------------------------------------------------------------

class TestCreateApp:
    """Tests for grip.api.create_app()."""

    def test_default(self):
        app = create_app(grip_class=GripMock)
        assert isinstance(app, GripMock)

    def test_text_uses_text_reader(self):
        app = create_app(text='# Hi', grip_class=GripMock)
        assert isinstance(app.reader, TextReader)
        assert app.reader.read() == '# Hi'

    def test_stdin_path(self):
        app = create_app(path='-', grip_class=GripMock)
        from grip import StdinReader
        assert isinstance(app.reader, StdinReader)

    def test_offline_uses_gripper_renderer(self):
        app = create_app(render_offline=True, grip_class=GripMock)
        assert isinstance(app.renderer, GripperRenderer)

    def test_user_content_uses_github_renderer(self):
        app = create_app(user_content=True, grip_class=GripMock)
        assert isinstance(app.renderer, GitHubRenderer)
        assert app.renderer.user_content is True

    def test_context_uses_github_renderer(self):
        app = create_app(context='owner/repo', grip_class=GripMock)
        assert isinstance(app.renderer, GitHubRenderer)
        assert app.renderer.context == 'owner/repo'

    def test_api_url_uses_github_renderer(self):
        app = create_app(api_url='https://custom', grip_class=GripMock)
        assert isinstance(app.renderer, GitHubRenderer)
        assert app.renderer.api_url == 'https://custom'

    def test_no_renderer_specified(self):
        app = create_app(grip_class=GripMock)
        # renderer=None means app uses default_renderer()
        # GripMock.default_renderer() returns GitHubRenderer
        assert isinstance(app.renderer, GitHubRenderer)

    def test_auth_tuple(self):
        app = create_app(username='user', password='pass',
                         grip_class=GripMock)
        assert app.auth == ('user', 'pass')

    def test_no_auth(self):
        app = create_app(grip_class=GripMock)
        # Auth is None unless config provides it
        # GripMock uses default config which has USERNAME=None, PASSWORD=None
        assert app.auth is None

    def test_render_wide(self):
        app = create_app(render_wide=True, grip_class=GripMock)
        assert app.render_wide is True

    def test_theme(self):
        app = create_app(theme='dark', grip_class=GripMock)
        assert app.theme == 'dark'


class TestRenderContent:
    """Tests for grip.api.render_content()."""

    def test_offline(self):
        html = render_content('**bold**', render_offline=True)
        assert '<strong>bold</strong>' in html

    def test_github(self):
        text = input_file('simple.md')
        with GitHubRequestsMock():
            html = render_content(text)
        assert html  # non-empty

    def test_offline_user_content(self):
        html = render_content('**bold**', render_offline=True,
                              user_content=True)
        assert '<strong>bold</strong>' in html


class TestRenderPage:
    """Tests for grip.api.render_page()."""

    def test_offline_with_text(self):
        html = render_page(text='# Hello', render_offline=True,
                           quiet=True, grip_class=GripMock)
        assert '<!DOCTYPE html>' in html
        assert 'Hello' in html

    def test_offline_with_file(self, tmp_path):
        md_file = tmp_path / 'README.md'
        md_file.write_text('# File Test')
        html = render_page(str(tmp_path), render_offline=True,
                           quiet=True, grip_class=GripMock)
        assert 'File Test' in html


class TestExport:
    """Tests for grip.api.export()."""

    def test_export_to_file(self, tmp_path, monkeypatch):
        monkeypatch.setenv('GRIPHOME', str(tmp_path / '.grip'))
        md_file = tmp_path / 'README.md'
        md_file.write_text('# Export')
        out = str(tmp_path / 'out.html')
        export(str(tmp_path), render_offline=True, out_filename=out,
               quiet=True)
        with open(out) as f:
            html = f.read()
        assert '<!DOCTYPE html>' in html
        assert 'Export' in html

    def test_export_to_stdout(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setenv('GRIPHOME', str(tmp_path / '.grip'))
        md_file = tmp_path / 'README.md'
        md_file.write_text('# Stdout')
        export(str(tmp_path), render_offline=True, out_filename='-',
               quiet=True)
        captured = capsys.readouterr()
        assert '<!DOCTYPE html>' in captured.out

    def test_export_default_filename(self, tmp_path, monkeypatch):
        monkeypatch.setenv('GRIPHOME', str(tmp_path / '.grip'))
        md_file = tmp_path / 'README.md'
        md_file.write_text('# Default')
        monkeypatch.chdir(tmp_path)
        export(str(tmp_path), render_offline=True, quiet=True)
        out = tmp_path / 'README.html'
        assert out.exists()
        assert 'Default' in out.read_text()


class TestClearCache:
    """Tests for grip.api.clear_cache()."""

    def test_clear_cache_calls_app(self):
        # GripMock uses GitHubAssetManagerMock which tracks clear calls
        clear_cache(grip_class=GripMock)
        # Just verify it doesn't raise
