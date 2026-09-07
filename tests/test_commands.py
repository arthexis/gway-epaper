from pathlib import Path

import pytest

from gway_epaper.commands import main
from gway_epaper.config import ConfigError


def test_explicit_config_wins(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    explicit = tmp_path / "explicit.toml"
    monkeypatch.setenv("EPAPER_CONFIG", str(tmp_path / "environment.toml"))

    assert main._resolve_config(explicit) == explicit


def test_environment_config_precedes_system_and_local(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    environment = tmp_path / "environment.toml"
    system = tmp_path / "system.toml"
    local = tmp_path / "epaper.toml"
    environment.write_text("[display]\n", encoding="utf-8")
    system.write_text("[display]\n", encoding="utf-8")
    local.write_text("[display]\n", encoding="utf-8")
    monkeypatch.setenv("EPAPER_CONFIG", str(environment))
    monkeypatch.setattr(main, "SYSTEM_CONFIG", system)
    monkeypatch.setattr(main, "LOCAL_CONFIG", local)

    assert main._resolve_config() == environment


def test_system_config_precedes_local(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    system = tmp_path / "system.toml"
    local = tmp_path / "epaper.toml"
    system.write_text("[display]\n", encoding="utf-8")
    local.write_text("[display]\n", encoding="utf-8")
    monkeypatch.delenv("EPAPER_CONFIG", raising=False)
    monkeypatch.setattr(main, "SYSTEM_CONFIG", system)
    monkeypatch.setattr(main, "LOCAL_CONFIG", local)

    assert main._resolve_config() == system


def test_local_config_is_fallback(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    system = tmp_path / "missing-system.toml"
    local = tmp_path / "epaper.toml"
    local.write_text("[display]\n", encoding="utf-8")
    monkeypatch.delenv("EPAPER_CONFIG", raising=False)
    monkeypatch.setattr(main, "SYSTEM_CONFIG", system)
    monkeypatch.setattr(main, "LOCAL_CONFIG", local)

    assert main._resolve_config() == local


def test_missing_default_config_has_actionable_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    system = tmp_path / "system.toml"
    local = tmp_path / "epaper.toml"
    monkeypatch.delenv("EPAPER_CONFIG", raising=False)
    monkeypatch.setattr(main, "SYSTEM_CONFIG", system)
    monkeypatch.setattr(main, "LOCAL_CONFIG", local)

    with pytest.raises(ConfigError, match="pass --config, set EPAPER_CONFIG"):
        main._resolve_config()
