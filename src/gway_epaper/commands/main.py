from __future__ import annotations

from pathlib import Path

from ..config import load_config
from ..runtime import build_runtime, run_forever
from ..systemd import (
    install_service,
    restart_service,
    service_status as get_service_status,
    start_service,
    stop_service,
    uninstall_service,
)


def validate(config: Path = Path("epaper.toml")) -> bool:
    """Validate the TOML configuration and return True when it is usable."""

    load_config(config)
    return True


def preview(config: Path = Path("epaper.toml")) -> str:
    """Poll configured scaffold sources once and return the text frame."""

    return build_runtime(config).poll_once()


def status(config: Path = Path("epaper.toml")) -> dict[str, object]:
    """Return a concise description of configured display and sources."""

    value = load_config(config)
    return {
        "display_driver": value.display.driver,
        "width": value.display.width,
        "lines": value.display.lines,
        "refresh_seconds": value.display.refresh_seconds,
        "sources": [
            {"name": source.name, "type": source.type} for source in value.sources
        ],
    }


def run(config: Path = Path("epaper.toml")) -> None:
    """Run the foreground aggregation loop using the configured backend."""

    run_forever(config)


def service_install(
    config: Path = Path("epaper.toml"),
    unit_path: Path = Path("/etc/systemd/system/gway-epaper.service"),
    user: str | None = None,
    enable: bool = True,
    start: bool = True,
) -> str:
    """Install and optionally enable/start the systemd service."""

    return str(
        install_service(
            config,
            unit_path=unit_path,
            user=user,
            enable=enable,
            start=start,
        )
    )


def service_uninstall(
    unit_path: Path = Path("/etc/systemd/system/gway-epaper.service"),
) -> bool:
    """Disable, stop, and remove the systemd service."""

    return uninstall_service(unit_path=unit_path)


def service_start(
    unit_path: Path = Path("/etc/systemd/system/gway-epaper.service"),
) -> None:
    """Start the installed systemd service."""

    start_service(unit_path=unit_path)


def service_stop(
    unit_path: Path = Path("/etc/systemd/system/gway-epaper.service"),
) -> None:
    """Stop the installed systemd service."""

    stop_service(unit_path=unit_path)


def service_restart(
    unit_path: Path = Path("/etc/systemd/system/gway-epaper.service"),
) -> None:
    """Restart the installed systemd service."""

    restart_service(unit_path=unit_path)


def service_status(
    unit_path: Path = Path("/etc/systemd/system/gway-epaper.service"),
) -> dict[str, object]:
    """Return machine-friendly systemd active/enabled state."""

    return get_service_status(unit_path=unit_path)
