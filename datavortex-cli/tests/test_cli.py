"""Tests de l'interface en ligne de commande `datavortex`.

Ces tests ne démarrent jamais le serveur réel (pas de bind réseau) : --version
et --help sortent avant que cli.main() importe .server (import différé,
volontairement, car il charge pandas/scikit-learn/tensorflow).
"""
import pytest

from datavortex import __version__
from datavortex.cli import build_parser, main
from datavortex.config import get_default_port


def test_version_string_matches_package():
    assert __version__ == "1.0.0"


def test_version_flag_prints_version_and_exits(capsys):
    with pytest.raises(SystemExit) as exc_info:
        main(["--version"])
    assert exc_info.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_help_flag_lists_all_documented_options(capsys):
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])
    assert exc_info.value.code == 0
    out = capsys.readouterr().out
    for flag in ("--port", "--host", "--open", "--help-browser", "--version"):
        assert flag in out


def test_default_port_is_8000_without_env_override(monkeypatch):
    monkeypatch.delenv("DATAVORTEX_PORT", raising=False)
    assert get_default_port() == 8000


def test_port_env_override(monkeypatch):
    monkeypatch.setenv("DATAVORTEX_PORT", "9500")
    assert get_default_port() == 9500


def test_invalid_port_env_falls_back_to_default(monkeypatch):
    monkeypatch.setenv("DATAVORTEX_PORT", "not-a-number")
    assert get_default_port() == 8000


def test_cli_port_flag_overrides_default():
    args = build_parser().parse_args(["--port", "9000"])
    assert args.port == 9000


def test_cli_short_flags():
    args = build_parser().parse_args(["-p", "9000", "-o"])
    assert args.port == 9000
    assert args.open is True


def test_cli_defaults_host_and_open():
    args = build_parser().parse_args([])
    assert args.host == "127.0.0.1"
    assert args.open is False
    assert args.help_browser is False
