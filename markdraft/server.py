"""
HTTP server for serving markdown previews.

Replaces Flask with stdlib http.server. All markdown rendering happens
client-side via marked.js, highlight.js, and mermaid.js.
"""

import html
import json
import mimetypes
import os
import posixpath
import threading
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from typing import Any
from urllib.parse import urlparse

from .assets import AssetCache
from .config import KATEX_CSS_URL
from .exceptions import ReadmeNotFoundError
from .readers import ReadmeReader
from .watcher import FileWatcher

# Ensure common font types are registered
mimetypes.add_type("application/x-font-woff", ".woff")
mimetypes.add_type("application/octet-stream", ".ttf")
mimetypes.add_type("application/javascript", ".js")

_STATIC_FILES = [
    "favicon.ico",
    "markdraft.css",
    "markdraft.js",
    "template.html",
    "octicons/octicons.css",
    "octicons/octicons.eot",
    "octicons/octicons.svg",
    "octicons/octicons.ttf",
    "octicons/octicons.woff",
    "octicons/octicons.woff2",
]


def _resolve_static_dir() -> str:
    """Resolve the static directory, extracting from zip if needed."""
    candidate = os.path.join(os.path.dirname(__file__), "static")
    if os.path.isdir(candidate):
        return candidate
    # Running from a zipapp — extract static files to a temp directory
    import importlib.resources
    import tempfile

    tmpdir = tempfile.mkdtemp(prefix="markdraft-static-")
    pkg = importlib.resources.files("markdraft") / "static"
    for relpath in _STATIC_FILES:
        data = (pkg / relpath).read_bytes()  # type: ignore[union-attr]
        dest = os.path.join(tmpdir, relpath)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "wb") as f:
            f.write(data)
    return tmpdir


STATIC_DIR = _resolve_static_dir()

# Page body variants for template.html
README_BODY = """\
                  <div id="readme" class="Box md Box--responsive">
                    {box_header}
                    <div class="Box-body px-5 pb-5">
                      <article id="markdraft-content" class="markdown-body entry-content container-lg">
                      </article>
                    </div>
                  </div>"""

BOX_HEADER = """\
<div class="Box-header d-flex border-bottom-0 flex-items-center flex-justify-between color-bg-default rounded-top-2">
                        <div class="d-flex flex-items-center">
                          <h2 class="Box-title">
                            {display_title}
                          </h2>
                        </div>
                      </div>"""

USER_CONTENT_BODY = """\
                  <div class="pull-discussion-timeline">
                    <div class="ml-0 pl-0 ml-md-6 pl-md-3">
                      <div class="TimelineItem pt-0">
                        <div class="timeline-comment-group TimelineItem-body my-0">
                          <div class="ml-n3 timeline-comment unminimized-comment comment previewable-edit editable-comment timeline-comment--caret reorderable-task-lists">
                            {comment_header}
                            <div class="edit-comment-hide">
                              <table class="d-block">
                                <tbody class="d-block">
                                  <tr class="d-block">
                                    <td class="d-block comment-body markdown-body" id="markdraft-content">
                                    </td>
                                  </tr>
                                </tbody>
                              </table>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>"""

COMMENT_HEADER = """\
<div class="timeline-comment-header clearfix d-block d-sm-flex">
                                <h3 class="timeline-comment-header-text f5 text-normal">
                                  <strong class="css-truncate expandable"><span class="author text-inherit css-truncate-target">{title}</span></strong>
                                </h3>
                              </div>"""


class PreviewServer(ThreadingHTTPServer):
    """Threaded HTTP server for markdown preview."""

    daemon_threads = True

    def __init__(
        self,
        address: tuple[str, int],
        reader: ReadmeReader,
        assets: AssetCache,
        config: dict[str, Any],
    ) -> None:
        self.reader = reader
        self.assets = assets
        self.server_config = config
        self.shutdown_event = threading.Event()
        self._template: str | None = None
        super().__init__(address, PreviewHandler)

    def get_template(self) -> str:
        if self._template is None:
            path = os.path.join(STATIC_DIR, "template.html")
            with open(path, "r", encoding="utf-8") as f:
                self._template = f.read()
        return self._template

    def build_page(self, subpath: str | None = None) -> str:
        """Build the HTML shell for a markdown page."""
        cfg = self.server_config
        filename = self.reader.filename_for(subpath) or ""
        title = cfg.get("title") or filename
        display_title = html.escape(title or filename)
        page_title = (
            html.escape(title)
            if cfg.get("title")
            else (html.escape(filename) + " - Markdraft" if filename else "Markdraft")
        )

        theme = cfg.get("theme", "light")
        data_color_mode = "dark" if theme == "dark" else "light"
        markdown_css = (
            "github-markdown-dark.css"
            if theme == "dark"
            else "github-markdown-light.css"
        )
        highlight_css = (
            "github-highlight-dark.min.css"
            if theme == "dark"
            else "github-highlight.min.css"
        )

        static_url = cfg.get("url_prefix", "/__") + "/static"
        content_path = cfg.get("url_prefix", "/__") + "/api/content"
        if subpath:
            content_path += "/" + subpath

        refresh_url = ""
        if cfg.get("autorefresh", True):
            refresh_url = cfg.get("url_prefix", "/__") + "/api/refresh"
            if subpath:
                refresh_url += "/" + subpath

        if cfg.get("user_content"):
            comment_header = ""
            if display_title:
                comment_header = COMMENT_HEADER.format(title=display_title)
            page_body = USER_CONTENT_BODY.format(comment_header=comment_header)
        else:
            box_header = ""
            if display_title:
                box_header = BOX_HEADER.format(display_title=display_title)
            page_body = README_BODY.format(box_header=box_header)

        return self.get_template().format(
            title=page_title,
            favicon_url=static_url + "/favicon.ico",
            static_url=static_url,
            markdown_css_url=static_url + "/" + markdown_css,
            highlight_css_url=static_url + "/" + highlight_css,
            katex_css_url=KATEX_CSS_URL,
            content_url=content_path,
            refresh_url=refresh_url,
            data_color_mode=data_color_mode,
            page_body=page_body,
        )


class PreviewHandler(BaseHTTPRequestHandler):
    """Request handler with routing."""

    server: PreviewServer  # type: ignore[assignment]

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        url_prefix: str = self.server.server_config.get("url_prefix", "/__")

        if path.startswith(url_prefix + "/api/content"):
            self._handle_api_content(path, url_prefix)
        elif path.startswith(url_prefix + "/api/refresh"):
            self._handle_api_refresh(path, url_prefix)
        elif path.startswith(url_prefix + "/static/"):
            self._handle_static(path, url_prefix)
        else:
            self._handle_page(path)

    def _handle_page(self, path: str) -> None:
        subpath = path.lstrip("/") or None

        try:
            normalized = self.server.reader.normalize_subpath(subpath)
        except ReadmeNotFoundError:
            self._send_error(404)
            return

        if normalized != subpath:
            self._send_redirect("/" + (normalized or ""))
            return

        # Binary files
        if self.server.reader.is_binary(subpath):
            try:
                raw = self.server.reader.read(subpath)
            except ReadmeNotFoundError:
                self._send_error(404)
                return
            data = raw if isinstance(raw, bytes) else raw.encode("utf-8")
            mimetype = (
                self.server.reader.mimetype_for(subpath) or "application/octet-stream"
            )
            self._send_bytes(200, data, mimetype)
            return

        # Verify the file exists before serving the shell
        try:
            self.server.reader.read(subpath)
        except ReadmeNotFoundError:
            self._send_error(404)
            return

        page = self.server.build_page(subpath)
        self._send_text(200, page, "text/html; charset=utf-8")

    def _handle_api_content(self, path: str, url_prefix: str) -> None:
        subpath = self._extract_subpath(path, url_prefix + "/api/content")
        try:
            text = self.server.reader.read(subpath)
            filename = self.server.reader.filename_for(subpath) or ""
        except ReadmeNotFoundError:
            self._send_error(404)
            return
        body = json.dumps({"text": text, "filename": filename})
        self._send_text(200, body, "application/json; charset=utf-8")

    def _handle_api_refresh(self, path: str, url_prefix: str) -> None:
        if not self.server.server_config.get("autorefresh", True):
            self._send_error(404)
            return
        subpath = self._extract_subpath(path, url_prefix + "/api/refresh")

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()

        watcher = FileWatcher(self.server.reader, subpath)
        try:
            for _ in watcher.watch(self.server.shutdown_event):
                self.wfile.write(b'data: {"updated": true}\r\n\r\n')
                self.wfile.flush()
                if not self.server.server_config.get("quiet"):
                    filename = self.server.reader.filename_for(subpath) or "file"
                    print(" * Change detected in {0}, refreshing".format(filename))
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _handle_static(self, path: str, url_prefix: str) -> None:
        prefix = url_prefix + "/static/"
        filename = path[len(prefix) :]
        if not filename or ".." in filename:
            self._send_error(404)
            return

        # Check bundled static dir first
        bundled = os.path.join(STATIC_DIR, filename)
        if os.path.isfile(bundled):
            self._serve_file(bundled)
            return

        # Check asset cache
        cached = self.server.assets.get_path(filename)
        if os.path.isfile(cached):
            self._serve_file(cached)
            return

        self._send_error(404)

    def _serve_file(self, filepath: str) -> None:
        mimetype, _ = mimetypes.guess_type(filepath)
        if mimetype is None:
            mimetype = "application/octet-stream"
        with open(filepath, "rb") as f:
            data = f.read()
        self._send_bytes(200, data, mimetype)

    def _extract_subpath(self, path: str, prefix: str) -> str | None:
        sub = path[len(prefix) :].strip("/")
        return sub or None

    def _send_text(self, code: int, text: str, content_type: str) -> None:
        self._send_bytes(code, text.encode("utf-8"), content_type)

    def _send_bytes(self, code: int, data: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_redirect(self, location: str) -> None:
        self.send_response(302)
        self.send_header("Location", location)
        self.end_headers()

    def _send_error(self, code: int) -> None:
        self.send_response(code)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(str(code).encode())

    def log_message(self, format: str, *args: Any) -> None:
        if not self.server.server_config.get("quiet"):
            super().log_message(format, *args)
