"""
Tests for the CLI and public API functions.
"""

import os
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


def test_bad_flag():
    with pytest.raises(CalledProcessError):
        run("--does-not-exist")


# ---------------------------------------------------------------------------
# Direct main() tests
# ---------------------------------------------------------------------------


class TestMainDirect:
    def test_version_flag(self, capsys):
        assert main(["-V"]) == 0
        assert version in capsys.readouterr().out

    def test_deprecated_a_flag(self, capsys):
        assert main(["-a"]) == 2

    def test_deprecated_p_flag(self, capsys):
        assert main(["-p"]) == 2

    def test_theme_invalid(self, capsys):
        assert main(["--theme=invalid", "--export", "."]) == 1
        assert "valid options" in capsys.readouterr().out

    def test_theme_light_export(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MARKDRAFT_HOME", str(tmp_path / ".markdraft"))
        (tmp_path / "README.md").write_text("# Hi")
        out = str(tmp_path / "out.html")
        assert main(["--theme=light", "--export", str(tmp_path), out, "--quiet"]) == 0

    def test_theme_dark_export(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MARKDRAFT_HOME", str(tmp_path / ".markdraft"))
        (tmp_path / "README.md").write_text("# Hi")
        out = str(tmp_path / "out.html")
        assert main(["--theme=dark", "--export", str(tmp_path), out, "--quiet"]) == 0

    def test_clear_flag(self, monkeypatch):
        cleared = []
        monkeypatch.setattr("markdraft.command.clear_cache", lambda: cleared.append(True))
        assert main(["--clear"]) == 0
        assert len(cleared) == 1

    def test_export_writes_file(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MARKDRAFT_HOME", str(tmp_path / ".markdraft"))
        (tmp_path / "README.md").write_text("# Export Test")
        out = str(tmp_path / "out.html")
        assert main(["--export", str(tmp_path), out, "--quiet"]) == 0
        with open(out) as f:
            assert "# Export Test" in f.read()

    def test_export_with_title(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MARKDRAFT_HOME", str(tmp_path / ".markdraft"))
        (tmp_path / "README.md").write_text("# Content")
        out = str(tmp_path / "out.html")
        assert main(["--export", "--title=Custom", str(tmp_path), out, "--quiet"]) == 0
        with open(out) as f:
            assert "Custom" in f.read()

    def test_missing_readme(self, tmp_path, capsys):
        empty = tmp_path / "empty"
        empty.mkdir()
        assert main(["--export", str(empty)]) == 1
        assert "Error" in capsys.readouterr().out

    def test_quiet_export(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setenv("MARKDRAFT_HOME", str(tmp_path / ".markdraft"))
        (tmp_path / "README.md").write_text("# Quiet")
        out = str(tmp_path / "out.html")
        assert main(["--export", "--quiet", str(tmp_path), out]) == 0
        captured = capsys.readouterr()
        assert "Exporting to" not in captured.err

    def test_no_inline_export(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MARKDRAFT_HOME", str(tmp_path / ".markdraft"))
        (tmp_path / "README.md").write_text("# No Inline")
        out = str(tmp_path / "out.html")
        assert main(["--export", "--no-inline", str(tmp_path), out, "--quiet"]) == 0
        with open(out) as f:
            assert "cdn.jsdelivr.net" in f.read()


# ---------------------------------------------------------------------------
# API integration tests
# ---------------------------------------------------------------------------


class TestApiExport:
    def test_export_default_filename(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MARKDRAFT_HOME", str(tmp_path / ".markdraft"))
        (tmp_path / "README.md").write_text("# Default")
        monkeypatch.chdir(tmp_path)
        from markdraft import export

        export(str(tmp_path), quiet=True)
        assert (tmp_path / "README.html").exists()

    def test_export_stdout(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setenv("MARKDRAFT_HOME", str(tmp_path / ".markdraft"))
        (tmp_path / "README.md").write_text("# Stdout")
        from markdraft import export

        export(str(tmp_path), out_filename="-", quiet=True)
        assert "<!DOCTYPE html>" in capsys.readouterr().out

    def test_clear_cache(self, tmp_path, monkeypatch):
        monkeypatch.setenv("MARKDRAFT_HOME", str(tmp_path))
        from markdraft import clear_cache

        clear_cache()  # should not raise
