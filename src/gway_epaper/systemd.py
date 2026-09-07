from __future__ import annotations

import getpass
import os
import subprocess
import sys
from pathlib import Path

DEFAULT_UNIT_PATH = Path("/etc/systemd/system/gway-epaper.service")


def _service_user(user: str | None) -> str:
    value = user or os.environ.get("SUDO_USER") or getpass.getuser()
    value = value.strip()
    if not value or any(character.isspace() for character in value):
        raise ValueError("service user must be a non-empty account name")
    return value


def _unit_arg(value: str | Path) -> str:
    text = str(value)
    if "\n" in text or "\r" in text:
        raise ValueError("systemd arguments must not contain newlines")
    text = text.replace("%", "%%").replace("\\", "\\\\").replace('"', '\\"')
    return f'"{text}"'


def render_unit(
    config: str | Path,
    *,
    python: str | Path | None = None,
    user: str | None = None,
) -> str:
    """Render the systemd unit for one gway-epaper service instance."""

    config_path = Path(config).expanduser().resolve()
    python_path = Path(python or sys.executable).expanduser().resolve()
    service_user = _service_user(user)
    return (
        "[Unit]\n"
        "Description=Gway ePaper display service\n"
        "Wants=network-online.target\n"
        "After=network-online.target\n\n"
        "[Service]\n"
        "Type=simple\n"
        f"User={service_user}\n"
        "Environment=PYTHONUNBUFFERED=1\n"
        f"ExecStart={_unit_arg(python_path)} -m gway_epaper.service {_unit_arg(config_path)}\n"
        "Restart=on-failure\n"
        "RestartSec=5s\n"
        "TimeoutStopSec=20s\n\n"
        "[Install]\n"
        "WantedBy=multi-user.target\n"
    )


def _systemctl(*arguments: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["systemctl", *arguments],
        check=check,
        text=True,
        capture_output=True,
    )


def install_service(
    config: str | Path = "epaper.toml",
    *,
    unit_path: str | Path = DEFAULT_UNIT_PATH,
    python: str | Path | None = None,
    user: str | None = None,
    enable: bool = True,
    start: bool = True,
) -> Path:
    """Install the systemd unit and optionally enable/start it."""

    config_path = Path(config).expanduser().resolve()
    if not config_path.is_file():
        raise FileNotFoundError(f"configuration not found: {config_path}")

    destination = Path(unit_path).expanduser()
    destination.parent.mkdir(parents=True, exist_ok=True)
    unit = render_unit(config_path, python=python, user=user)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(unit, encoding="utf-8")
    os.replace(temporary, destination)

    _systemctl("daemon-reload")
    if enable:
        _systemctl("enable", destination.name)
    if start:
        _systemctl("restart", destination.name)
    return destination


def uninstall_service(
    *,
    unit_path: str | Path = DEFAULT_UNIT_PATH,
) -> bool:
    """Stop/disable the service, remove its unit, and reload systemd."""

    destination = Path(unit_path).expanduser()
    existed = destination.exists()
    _systemctl("disable", "--now", destination.name, check=False)
    if existed:
        destination.unlink()
    _systemctl("daemon-reload")
    _systemctl("reset-failed", destination.name, check=False)
    return existed


def start_service(*, unit_path: str | Path = DEFAULT_UNIT_PATH) -> None:
    _systemctl("start", Path(unit_path).name)


def stop_service(*, unit_path: str | Path = DEFAULT_UNIT_PATH) -> None:
    _systemctl("stop", Path(unit_path).name)


def restart_service(*, unit_path: str | Path = DEFAULT_UNIT_PATH) -> None:
    _systemctl("restart", Path(unit_path).name)


def service_status(*, unit_path: str | Path = DEFAULT_UNIT_PATH) -> dict[str, object]:
    """Return machine-friendly systemd active/enabled state."""

    name = Path(unit_path).name
    active = _systemctl("is-active", name, check=False)
    enabled = _systemctl("is-enabled", name, check=False)
    return {
        "unit": name,
        "active": active.returncode == 0,
        "active_state": active.stdout.strip() or active.stderr.strip(),
        "enabled": enabled.returncode == 0,
        "enabled_state": enabled.stdout.strip() or enabled.stderr.strip(),
    }
