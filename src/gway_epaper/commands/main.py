from __future__ import annotations

from pathlib import Path

from ..config import load_config
from ..displays import build_display
from ..runtime import build_runtime, run_forever


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


def write(text: str, config: Path = Path("epaper.toml")) -> bool:
    """Write arbitrary text directly to the configured display."""

    value = load_config(config)
    display = build_display(value.display)
    try:
        return bool(display.render(text.splitlines() or [""]))
    finally:
        close = getattr(display, "close", None)
        if close is not None:
            close()


def clear(config: Path = Path("epaper.toml")) -> bool:
    """Clear the configured display."""

    value = load_config(config)
    display = build_display(value.display)
    try:
        clear_display = getattr(display, "clear", None)
        if clear_display is not None:
            return bool(clear_display())
        return bool(display.render([""]))
    finally:
        close = getattr(display, "close", None)
        if close is not None:
            close()
