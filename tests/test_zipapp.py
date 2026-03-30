"""
Tests for the zipapp (.pyz) single-file distribution.

Builds a real markdraft.pyz and exercises it via subprocess to verify
that static file extraction, export, and serving all work from inside
a zip archive.
"""

import json
import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="session")
def pyz_path(tmp_path_factory):
    """Build markdraft.pyz once for the entire test session."""
    tmp = tmp_path_factory.mktemp("zipapp")
    staging = tmp / "staging"
    staging.mkdir()

    # Copy package into staging
    src = os.path.join(REPO_ROOT, "markdraft")
    dst = staging / "markdraft"
    import shutil

    shutil.copytree(src, dst)
    shutil.copy(os.path.join(src, "__main__.py"), staging / "__main__.py")

    pyz = tmp / "markdraft.pyz"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "zipapp",
            str(staging),
            "-o",
            str(pyz),
            "-p",
            "/usr/bin/env python3",
        ],
        check=True,
    )
    return str(pyz)


def run_pyz(pyz_path, *args, timeout=10):
    """Run the zipapp with the given arguments and return (returncode, stdout, stderr)."""
    result = subprocess.run(
        [sys.executable, str(pyz_path)] + list(args),
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return result.returncode, result.stdout, result.stderr


class TestZipappStructure:
    """Verify the zipapp internal layout matches what release.yml produces."""

    def test_no_nested_package(self, pyz_path):
        """The package must be at markdraft/, not markdraft/markdraft/."""
        import zipfile

        with zipfile.ZipFile(pyz_path) as z:
            names = z.namelist()
        assert "markdraft/__init__.py" in names
        assert "markdraft/markdraft/__init__.py" not in names

    def test_static_files_included(self, pyz_path):
        """All required static files must be present in the zipapp."""
        import zipfile

        with zipfile.ZipFile(pyz_path) as z:
            names = z.namelist()
        for f in [
            "markdraft/static/template.html",
            "markdraft/static/markdraft.css",
            "markdraft/static/markdraft.js",
            "markdraft/static/favicon.ico",
        ]:
            assert f in names, f"missing {f}"


class TestZipappCLI:
    """Basic CLI operations from the zipapp."""

    def test_version(self, pyz_path):
        code, out, _ = run_pyz(pyz_path, "--version")
        assert code == 0
        assert "Markdraft" in out

    def test_help(self, pyz_path):
        code, out, _ = run_pyz(pyz_path, "-h")
        assert code == 0
        assert "draft" in out.lower()

    def test_missing_readme(self, pyz_path, tmp_path):
        empty = tmp_path / "empty"
        empty.mkdir()
        code, out, _ = run_pyz(pyz_path, "--export", str(empty))
        assert code == 1
        assert "Error" in out


class TestZipappExport:
    """Export from the zipapp produces valid self-contained HTML."""

    def test_export_inline(self, pyz_path, tmp_path):
        md = tmp_path / "README.md"
        md.write_text("# Hello from zipapp\n\nSome **bold** text.")
        out = tmp_path / "out.html"
        code, _, _ = run_pyz(pyz_path, "--export", str(tmp_path), str(out), "--quiet")
        assert code == 0
        html = out.read_text()
        assert "<!DOCTYPE html>" in html
        assert "# Hello from zipapp" in html
        assert "markdraft-source" in html
        # markdraft.js should be inlined
        assert "marked.parse" in html

    def test_export_no_inline(self, pyz_path, tmp_path):
        md = tmp_path / "README.md"
        md.write_text("# CDN test")
        out = tmp_path / "out.html"
        code, _, _ = run_pyz(
            pyz_path, "--export", "--no-inline", str(tmp_path), str(out), "--quiet"
        )
        assert code == 0
        html = out.read_text()
        assert "cdn.jsdelivr.net" in html

    def test_export_dark_theme(self, pyz_path, tmp_path):
        md = tmp_path / "README.md"
        md.write_text("# Dark")
        out = tmp_path / "out.html"
        code, _, _ = run_pyz(
            pyz_path, "--export", "--theme=dark", str(tmp_path), str(out), "--quiet"
        )
        assert code == 0
        assert 'data-color-mode="dark"' in out.read_text()

    def test_export_with_title(self, pyz_path, tmp_path):
        md = tmp_path / "README.md"
        md.write_text("# Content")
        out = tmp_path / "out.html"
        code, _, _ = run_pyz(
            pyz_path, "--export", "--title=Custom", str(tmp_path), str(out), "--quiet"
        )
        assert code == 0
        assert "<title>Custom</title>" in out.read_text()

    def test_export_to_stdout(self, pyz_path, tmp_path):
        md = tmp_path / "README.md"
        md.write_text("# Stdout")
        code, out, _ = run_pyz(pyz_path, "--export", str(tmp_path), "-", "--quiet")
        assert code == 0
        assert "<!DOCTYPE html>" in out


class TestZipappServer:
    """The zipapp can serve files over HTTP."""

    def test_serves_html_and_api(self, pyz_path, tmp_path):
        md = tmp_path / "README.md"
        md.write_text("# Server test\n\nHello from **zipapp**.")

        # Start server in background
        proc = subprocess.Popen(
            [sys.executable, str(pyz_path), str(tmp_path), "127.0.0.1:0", "--quiet"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            # Read the port from stderr (server prints "Serving on ...")
            # With --quiet, it won't print. Use a known port instead.
            proc.terminate()
            proc.wait(timeout=3)
        except Exception:
            proc.kill()

        # Since we can't easily grab the random port from --quiet mode,
        # test with a fixed port
        port = 16419
        proc = subprocess.Popen(
            [sys.executable, str(pyz_path), str(tmp_path), "127.0.0.1:{}".format(port)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            # Wait for server to start
            for _ in range(30):
                try:
                    resp = urllib.request.urlopen(
                        "http://127.0.0.1:{}/".format(port), timeout=1
                    )
                    break
                except (urllib.error.URLError, ConnectionRefusedError):
                    time.sleep(0.2)
            else:
                pytest.fail("Server didn't start within 6 seconds")

            # Test page
            html = resp.read().decode()
            assert "<!DOCTYPE html>" in html
            assert "markdraft-content" in html
            assert "markdraft.js" in html

            # Test API
            api_resp = urllib.request.urlopen(
                "http://127.0.0.1:{}/__/api/content".format(port), timeout=2
            )
            data = json.loads(api_resp.read())
            assert data["text"] == "# Server test\n\nHello from **zipapp**."

            # Test static files
            css_resp = urllib.request.urlopen(
                "http://127.0.0.1:{}/__/static/markdraft.css".format(port), timeout=2
            )
            assert b".preview-page" in css_resp.read()

            js_resp = urllib.request.urlopen(
                "http://127.0.0.1:{}/__/static/markdraft.js".format(port), timeout=2
            )
            assert b"marked" in js_resp.read()

        finally:
            proc.terminate()
            proc.wait(timeout=3)
