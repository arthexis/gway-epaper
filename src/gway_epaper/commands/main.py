from __future__ import annotations

import os
from pathlib import Path

from ..config import ConfigError, DisplayConfig, load_config
from ..displays import build_display
from ..runtime import build_runtime, run_forever
from ..systemd import (
    install_service,
    restart_service,
    start_service,
    stop_service,
    uninstall_service,
)
from ..systemd import service_status as get_service_status

SYSTEM_CONFIG = Path("/etc/gway-epaper/epaper.toml")
LOCAL_CONFIG = Path("epaper.toml")
DEFAULT_DIRECT_DISPLAY = DisplayConfig(driver="waveshare_2in13_v4")


def _resolve_config(config: Path | None = None) -> Path:
    """Resolve config from an explicit path, environment, system, then cwd."""

    if config is not None:
        return Path(config).expanduser()

    environment = os.environ.get("EPAPER_CONFIG", "").strip()
    if environment:
        return Path(environment).expanduser()

    if SYSTEM_CONFIG.is_file():
        return SYSTEM_CONFIG
    if LOCAL_CONFIG.is_file():
        return LOCAL_CONFIG

    raise ConfigError(
        "configuration not found; pass --config, set EPAPER_CONFIG, or create "
        f"{SYSTEM_CONFIG} or {LOCAL_CONFIG}"
    )


def _direct_display_config(config: Path | None = None) -> DisplayConfig:
    """Resolve direct-command display config, falling back to the supported HAT."""

    try:
        return load_config(_resolve_config(config)).display
    except ConfigError:
        if config is not None or os.environ.get("EPAPER_CONFIG", "").strip():
            raise
        return DEFAULT_DIRECT_DISPLAY


def validate(config: Path | None = None) -> bool:
    """Validate the resolved TOML configuration and return True when usable."""

    load_config(_resolve_config(config))
    return True


def preview(config: Path | None = None) -> str:
    """Poll configured scaffold sources once and return the text frame."""

    return build_runtime(_resolve_config(config)).poll_once()


def status(config: Path | None = None) -> dict[str, object]:
    """Return a concise description of configured display and sources."""

    value = load_config(_resolve_config(config))
    return {
        "display_driver": value.display.driver,
        "width": value.display.width,
        "lines": value.display.lines,
        "refresh_seconds": value.display.refresh_seconds,
        "sources": [
            {"name": source.name, "type": source.type} for source in value.sources
        ],
    }


def run(config: Path | None = None) -> None:
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
    run_forever(_resolve_config(config))


def write(text: str, config: Path | None = None) -> bool:
    """Write arbitrary text directly to the configured or default ePaper display."""

    display = build_display(_direct_display_config(config))
    try:
        return bool(display.render(text.splitlines() or [""]))
    finally:
        close = getattr(display, "close", None)
        if close is not None:
            close()


def clear(config: Path | None = None) -> bool:
    """Clear the configured or default ePaper display."""

    display = build_display(_direct_display_config(config))
    try:
        clear_display = getattr(display, "clear", None)
        if clear_display is not None:
            return bool(clear_display())
        return bool(display.render([""]))
    finally:
        close = getattr(display, "close", None)
        if close is not None:
            close()
