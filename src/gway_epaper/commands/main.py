from __future__ import annotations

from pathlib import Path

from ..config import load_config
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
            {"name": source.name, "type": source.type}
            for source in value.sources
        ],
    }


def run(config: Path = Path("epaper.toml")) -> None:
    """Run the foreground aggregation loop using the configured backend."""

    run_forever(config)
