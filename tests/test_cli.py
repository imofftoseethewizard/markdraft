"""
Tests the Grip command-line interface.

Subprocess tests verify the actual CLI binary. Direct main() tests exercise
argument parsing and flag handling without spawning a process.
"""

import os
import sys
from subprocess import PIPE, STDOUT, CalledProcessError, Popen

import pytest

from grip.command import main, version


def run(*args, **kwargs):
    command = kwargs.pop('command', 'grip')
    stdin = kwargs.pop('stdin', None)

    cmd = [command] + list(args)
    p = Popen(cmd, stdin=PIPE, stdout=PIPE, stderr=STDOUT,
              universal_newlines=True)
    output, _ = p.communicate(input=stdin)
    p.stdin.close()
    returncode = p.wait()
    if returncode != 0:
        raise CalledProcessError(returncode, cmd, output=output)
    return output


# ---------------------------------------------------------------------------
# Subprocess CLI tests
# ---------------------------------------------------------------------------

def test_help():
    output = run('-h')
    assert 'grip' in output.lower()
    assert 'usage' in output.lower() or 'options' in output.lower()


def test_version():
    assert run('-V') == version + '\n'


def test_bad_command():
    with pytest.raises(CalledProcessError) as excinfo:
        run('--does-not-exist')
    assert excinfo.value.returncode != 0


# ---------------------------------------------------------------------------
# Direct main() tests
# ---------------------------------------------------------------------------

class TestMainDirect:
    """Exercise main() with argv for argument parsing coverage."""

    def test_version_flag(self, capsys):
        assert main(['-V']) == 0
        assert version in capsys.readouterr().out

    def test_deprecated_address_flag(self, capsys):
        assert main(['-a']) == 2
        assert 'instead of -a' in capsys.readouterr().out

    def test_deprecated_port_flag(self, capsys):
        assert main(['-p']) == 2
        assert 'instead of -p' in capsys.readouterr().out

    def test_theme_invalid(self, capsys):
        assert main(['--theme=invalid', '--export', '.']) == 1
        assert 'valid options' in capsys.readouterr().out

    def test_theme_light(self, tmp_path):
        md = tmp_path / 'README.md'
        md.write_text('# Hi')
        out = str(tmp_path / 'out.html')
        result = main(['--theme=light', '--export', str(tmp_path),
                        out, '--quiet'])
        assert result == 0

    def test_theme_dark(self, tmp_path):
        md = tmp_path / 'README.md'
        md.write_text('# Hi')
        out = str(tmp_path / 'out.html')
        result = main(['--theme=dark', '--export', str(tmp_path),
                        out, '--quiet'])
        assert result == 0

    def test_clear_flag(self, monkeypatch):
        cleared = []
        monkeypatch.setattr('grip.command.clear_cache',
                            lambda **kwargs: cleared.append(True))
        assert main(['--clear']) == 0
        assert len(cleared) == 1

    def test_export_flag(self, tmp_path):
        md = tmp_path / 'README.md'
        md.write_text('# Export Test')
        out = str(tmp_path / 'out.html')
        result = main(['--export', str(tmp_path), out, '--quiet'])
        assert result == 0
        assert os.path.exists(out)
        with open(out) as f:
            assert 'Export Test' in f.read()

    def test_export_with_title(self, tmp_path):
        md = tmp_path / 'README.md'
        md.write_text('# Content')
        out = str(tmp_path / 'out.html')
        result = main(['--export', '--title=Custom Title', str(tmp_path),
                        out, '--quiet'])
        assert result == 0
        with open(out) as f:
            html = f.read()
        assert 'Custom Title' in html

    def test_missing_readme(self, tmp_path, capsys):
        empty = tmp_path / 'empty'
        empty.mkdir()
        result = main(['--export', str(empty)])
        assert result == 1
        assert 'Error' in capsys.readouterr().out

    def test_quiet_flag(self, tmp_path, capsys):
        md = tmp_path / 'README.md'
        md.write_text('# Quiet')
        out = str(tmp_path / 'out.html')
        result = main(['--export', '--quiet', str(tmp_path), out])
        assert result == 0
        captured = capsys.readouterr()
        assert 'Exporting to' not in captured.err

    def test_export_no_inline(self, tmp_path):
        md = tmp_path / 'README.md'
        md.write_text('# No Inline')
        out = str(tmp_path / 'out.html')
        result = main(['--export', '--no-inline', str(tmp_path),
                        out, '--quiet'])
        assert result == 0
        with open(out) as f:
            html = f.read()
        assert '<!DOCTYPE html>' in html
