from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from gway_epaper import service, systemd


def completed(*args: str, returncode: int = 0, stdout: str = ""):
    return subprocess.CompletedProcess(args, returncode, stdout=stdout, stderr="")


def test_render_unit_uses_absolute_paths_and_restart_policy(tmp_path: Path) -> None:
    config = tmp_path / "epaper.toml"
    python = tmp_path / "venv" / "bin" / "python"
    config.write_text("[display]\n", encoding="utf-8")

    unit = systemd.render_unit(config, python=python, user="display")

    assert (
        f'ExecStart="{python.resolve()}" -m gway_epaper.service '
        f'"{config.resolve()}"'
        in unit
    )
    assert "User=display\n" in unit
    assert "Restart=on-failure\n" in unit
    assert "RestartSec=5s\n" in unit
    assert "WantedBy=multi-user.target\n" in unit


def test_render_unit_rejects_invalid_user(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="service user"):
        systemd.render_unit(tmp_path / "epaper.toml", user="bad user")


def test_install_writes_unit_and_reloads_enables_restarts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = tmp_path / "epaper.toml"
    config.write_text("[display]\n", encoding="utf-8")
    unit_path = tmp_path / "systemd" / "gway-epaper.service"
    calls: list[tuple[tuple[str, ...], bool]] = []

    def fake_systemctl(*args: str, check: bool = True):
        calls.append((args, check))
        return completed(*args)

    monkeypatch.setattr(systemd, "_systemctl", fake_systemctl)

    result = systemd.install_service(
        config,
        unit_path=unit_path,
        python="/usr/bin/python3",
        user="display",
    )

    assert result == unit_path
    assert unit_path.exists()
    assert not unit_path.with_suffix(".service.tmp").exists()
    assert "User=display" in unit_path.read_text(encoding="utf-8")
    assert calls == [
        (("daemon-reload",), True),
        (("enable", "gway-epaper.service"), True),
        (("restart", "gway-epaper.service"), True),
    ]


def test_install_can_skip_enable_and_start(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = tmp_path / "epaper.toml"
    config.write_text("[display]\n", encoding="utf-8")
    calls: list[tuple[str, ...]] = []

    def fake_systemctl(*args: str, check: bool = True):
        calls.append(args)
        return completed(*args)

    monkeypatch.setattr(systemd, "_systemctl", fake_systemctl)
    systemd.install_service(
        config,
        unit_path=tmp_path / "gway-epaper.service",
        user="display",
        enable=False,
        start=False,
    )

    assert calls == [("daemon-reload",)]


def test_uninstall_is_idempotent_and_reloads_systemd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    unit_path = tmp_path / "gway-epaper.service"
    unit_path.write_text("unit\n", encoding="utf-8")
    calls: list[tuple[tuple[str, ...], bool]] = []

    def fake_systemctl(*args: str, check: bool = True):
        calls.append((args, check))
        return completed(*args)

    monkeypatch.setattr(systemd, "_systemctl", fake_systemctl)

    assert systemd.uninstall_service(unit_path=unit_path) is True
    assert not unit_path.exists()
    assert systemd.uninstall_service(unit_path=unit_path) is False
    assert calls[:3] == [
        (("disable", "--now", "gway-epaper.service"), False),
        (("daemon-reload",), True),
        (("reset-failed", "gway-epaper.service"), False),
    ]


def test_service_status_reports_active_and_enabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_systemctl(*args: str, check: bool = True):
        if args[0] == "is-active":
            return completed(*args, stdout="active\n")
        return completed(*args, returncode=1, stdout="disabled\n")

    monkeypatch.setattr(systemd, "_systemctl", fake_systemctl)

    assert systemd.service_status() == {
        "unit": "gway-epaper.service",
        "active": True,
        "active_state": "active",
        "enabled": False,
        "enabled_state": "disabled",
    }


def test_internal_service_runner_requires_one_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[Path] = []
    monkeypatch.setattr(service, "run_forever", lambda path: seen.append(path))

    assert service.main(["/etc/gway-epaper/epaper.toml"]) == 0
    assert seen == [Path("/etc/gway-epaper/epaper.toml")]

    with pytest.raises(SystemExit, match="usage"):
        service.main([])
