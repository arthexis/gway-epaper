from pathlib import Path

import gway_epaper.lifecycle as lifecycle


def test_upgrade_restarts_existing_gway_service(monkeypatch, tmp_path: Path) -> None:
    unit_directory = tmp_path / "systemd"
    unit_directory.mkdir()
    (unit_directory / lifecycle.SERVICE_UNIT).write_text("[Service]\n", encoding="utf-8")
    calls: list[list[str]] = []

    monkeypatch.setattr(lifecycle, "SYSTEMD_UNIT_DIRECTORY", unit_directory)
    monkeypatch.setattr(lifecycle.platform, "system", lambda: "Linux")
    monkeypatch.setattr(lifecycle, "_install_waveshare_driver", lambda: None)
    monkeypatch.setattr(lifecycle, "_run", lambda command: calls.append(command))

    lifecycle.upgrade()

    assert calls == [["systemctl", "try-restart", "gway-epaper.service"]]


def test_upgrade_does_not_create_or_restart_missing_service(
    monkeypatch, tmp_path: Path
) -> None:
    unit_directory = tmp_path / "systemd"
    unit_directory.mkdir()
    calls: list[list[str]] = []

    monkeypatch.setattr(lifecycle, "SYSTEMD_UNIT_DIRECTORY", unit_directory)
    monkeypatch.setattr(lifecycle.platform, "system", lambda: "Linux")
    monkeypatch.setattr(lifecycle, "_install_waveshare_driver", lambda: None)
    monkeypatch.setattr(lifecycle, "_run", lambda command: calls.append(command))

    lifecycle.upgrade()

    assert calls == []


def test_upgrade_skips_systemd_on_non_linux(monkeypatch, tmp_path: Path) -> None:
    unit_directory = tmp_path / "systemd"
    unit_directory.mkdir()
    (unit_directory / lifecycle.SERVICE_UNIT).write_text("[Service]\n", encoding="utf-8")
    calls: list[list[str]] = []

    monkeypatch.setattr(lifecycle, "SYSTEMD_UNIT_DIRECTORY", unit_directory)
    monkeypatch.setattr(lifecycle.platform, "system", lambda: "Windows")
    monkeypatch.setattr(lifecycle, "_install_waveshare_driver", lambda: None)
    monkeypatch.setattr(lifecycle, "_run", lambda command: calls.append(command))

    lifecycle.upgrade()

    assert calls == []
