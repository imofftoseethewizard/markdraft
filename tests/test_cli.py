"""
Tests the Markdraft command-line interface.
"""

import os
import sys
from subprocess import PIPE, STDOUT, CalledProcessError, Popen

import pytest

from markdraft.command import main, version


def run(*args, **kwargs):
    command = kwargs.pop("command", "draft")
    cmd = [command] + list(args)
    p = Popen(cmd, stdin=PIPE, stdout=PIPE, stderr=STDOUT, universal_newlines=True)
    output, _ = p.communicate()
    p.stdin.close()
    returncode = p.wait()
    if returncode != 0:
        raise CalledProcessError(returncode, cmd, output=output)
    return output


# ---------------------------------------------------------------------------
# Subprocess tests
# ---------------------------------------------------------------------------


def test_help():
    output = run("-h")
    assert "draft" in output.lower()


def test_version():
    assert run("-V") == version + "\n"


def test_bad_command():
    with pytest.raises(CalledProcessError):
        run("--does-not-exist")


# ---------------------------------------------------------------------------
# Direct main() tests
# ---------------------------------------------------------------------------


class TestMainDirect:

    def test_version_flag(self, capsys):
        assert main(["-V"]) == 0
        assert version in capsys.readouterr().out

    def test_deprecated_address_flag(self, capsys):
        assert main(["-a"]) == 2

    def test_deprecated_port_flag(self, capsys):
        assert main(["-p"]) == 2

    def test_theme_invalid(self, capsys):
        assert main(["--theme=invalid", "--export", "."]) == 1
        assert "valid options" in capsys.readouterr().out

    def test_theme_light(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MARKDRAFT_HOME", str(tmp_path / ".markdraft"))
        md = tmp_path / "README.md"
        md.write_text("# Hi")
        out = str(tmp_path / "out.html")
        assert main(["--theme=light", "--export", str(tmp_path), out, "--quiet"]) == 0

    def test_theme_dark(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MARKDRAFT_HOME", str(tmp_path / ".markdraft"))
        md = tmp_path / "README.md"
        md.write_text("# Hi")
        out = str(tmp_path / "out.html")
        assert main(["--theme=dark", "--export", str(tmp_path), out, "--quiet"]) == 0

    def test_clear_flag(self, monkeypatch):
        cleared = []
        monkeypatch.setattr("markdraft.command.clear_cache", lambda: cleared.append(True))
        assert main(["--clear"]) == 0
        assert len(cleared) == 1

    def test_export_flag(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MARKDRAFT_HOME", str(tmp_path / ".markdraft"))
        md = tmp_path / "README.md"
        md.write_text("# Export Test")
        out = str(tmp_path / "out.html")
        assert main(["--export", str(tmp_path), out, "--quiet"]) == 0
        assert os.path.exists(out)
        with open(out) as f:
            assert "# Export Test" in f.read()

    def test_export_with_title(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MARKDRAFT_HOME", str(tmp_path / ".markdraft"))
        md = tmp_path / "README.md"
        md.write_text("# Content")
        out = str(tmp_path / "out.html")
        assert main(["--export", "--title=Custom", str(tmp_path), out, "--quiet"]) == 0
        with open(out) as f:
            assert "Custom" in f.read()

    def test_missing_readme(self, tmp_path, capsys):
        empty = tmp_path / "empty"
        empty.mkdir()
        assert main(["--export", str(empty)]) == 1
        assert "Error" in capsys.readouterr().out

    def test_quiet_flag(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setenv("MARKDRAFT_HOME", str(tmp_path / ".markdraft"))
        md = tmp_path / "README.md"
        md.write_text("# Quiet")
        out = str(tmp_path / "out.html")
        assert main(["--export", "--quiet", str(tmp_path), out]) == 0

    def test_export_no_inline(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MARKDRAFT_HOME", str(tmp_path / ".markdraft"))
        md = tmp_path / "README.md"
        md.write_text("# No Inline")
        out = str(tmp_path / "out.html")
        assert main(["--export", "--no-inline", str(tmp_path), out, "--quiet"]) == 0
        with open(out) as f:
            html = f.read()
        assert "<!DOCTYPE html>" in html
        assert "cdn.jsdelivr.net" in html
