"""
Public API for Grip.
"""

import os
import sys

from . import __version__
from .assets import AssetCache
from .browser import start_browser_when_ready
from .config import (
    DEFAULT_GRIPHOME, CACHE_DIRECTORY, HOST, PORT,
    AUTOREFRESH, QUIET, load_user_settings)
from .exceptions import ReadmeNotFoundError
from .export import export_page
from .readers import DirectoryReader, StdinReader, TextReader
from .server import GripServer


def _resolve_config(host=None, port=None, autorefresh=None, quiet=None,
                    theme='light', title=None, user_content=False,
                    wide=False, grip_url='/__'):
    """Build a config dict from arguments + user settings."""
    settings = load_user_settings()
    return dict(
        host=host or settings.get('HOST', HOST),
        port=port if port is not None else settings.get('PORT', PORT),
        autorefresh=(autorefresh if autorefresh is not None
                     else settings.get('AUTOREFRESH', AUTOREFRESH)),
        quiet=quiet if quiet is not None else settings.get('QUIET', QUIET),
        theme=theme,
        title=title,
        user_content=user_content,
        wide=wide,
        grip_url=grip_url,
    )


def _make_reader(path=None, text=None):
    """Create the appropriate reader for the given arguments."""
    if text is not None:
        display_filename = DirectoryReader(path, True).filename_for(None)
        return TextReader(text, display_filename)
    elif path == '-':
        return StdinReader()
    else:
        return DirectoryReader(path)


def _make_cache():
    """Create an AssetCache with the default cache path."""
    griphome = os.path.expanduser(
        os.environ.get('GRIPHOME', DEFAULT_GRIPHOME))
    cache_dir = CACHE_DIRECTORY.format(version=__version__)
    cache_path = os.path.join(griphome, cache_dir)
    return AssetCache(cache_path)


def serve(path=None, host=None, port=None, user_content=False,
          wide=False, title=None, autorefresh=True,
          browser=False, quiet=None, theme='light'):
    """Start the preview server."""
    reader = _make_reader(path)
    assets = _make_cache()
    config = _resolve_config(
        host, port, autorefresh, quiet, theme, title, user_content, wide)

    assets.ensure_cached(quiet=config['quiet'])

    address = (config['host'], config['port'])
    server = GripServer(address, reader, assets, config)

    if not config['quiet']:
        print(' * Serving on http://{0}:{1}/'.format(*address),
              file=sys.stderr)

    browser_thread = None
    if browser:
        browser_thread = start_browser_when_ready(
            config['host'], config['port'], server.shutdown_event)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        if not config['quiet']:
            print(' * Shutting down...', file=sys.stderr)
        server.shutdown_event.set()
        server.server_close()
        if browser_thread:
            browser_thread.join(timeout=1)


def export(path=None, user_content=False, wide=False,
           render_inline=True, out_filename=None, title=None,
           quiet=False, theme='light'):
    """Export rendered markdown to an HTML file."""
    reader = _make_reader(path)
    assets = _make_cache()
    assets.ensure_cached(quiet=quiet)

    export_to_stdout = out_filename == '-'
    if out_filename is None:
        if path == '-':
            export_to_stdout = True
        else:
            filetitle, _ = os.path.splitext(
                os.path.relpath(reader.root_filename))
            out_filename = '{0}.html'.format(filetitle)

    if not export_to_stdout and not quiet:
        print('Exporting to', out_filename, file=sys.stderr)

    out = '-' if export_to_stdout else out_filename
    export_page(reader, None, assets, out_file=out, inline=render_inline,
                title=title, theme=theme, user_content=user_content,
                wide=wide, quiet=quiet)


def clear_cache():
    """Clear the cached assets."""
    assets = _make_cache()
    assets.clear()
    print('Cache cleared.')
