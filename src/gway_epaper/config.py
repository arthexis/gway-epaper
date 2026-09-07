from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class DisplayConfig:
    driver: str = "text"
    width: int = 40
    lines: int = 12
    refresh_seconds: float = 2.0
    font_size: int = 12
    margin: int = 4


@dataclass(frozen=True)
class PrinterConfig:
    prefix_source: bool = True
    timestamp: bool = False


@dataclass(frozen=True)
class SourceConfig:
    name: str
    type: str
    values: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EpaperConfig:
    display: DisplayConfig
    printer: PrinterConfig
    sources: tuple[SourceConfig, ...]


def _positive_int(value: Any, label: str) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"{label} must be an integer") from exc
    if result <= 0:
        raise ConfigError(f"{label} must be greater than zero")
    return result


def _positive_float(value: Any, label: str) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"{label} must be a number") from exc
    if result <= 0:
        raise ConfigError(f"{label} must be greater than zero")
    return result


def load_config(path: str | Path = "epaper.toml") -> EpaperConfig:
    config_path = Path(path).expanduser()
    try:
        with config_path.open("rb") as stream:
            data = tomllib.load(stream)
    except FileNotFoundError as exc:
        raise ConfigError(f"configuration not found: {config_path}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"invalid TOML in {config_path}: {exc}") from exc

    display_data = data.get("display", {})
    printer_data = data.get("printer", {})
    sources_data = data.get("sources", [])

    if not isinstance(display_data, dict):
        raise ConfigError("[display] must be a table")
    if not isinstance(printer_data, dict):
        raise ConfigError("[printer] must be a table")
    if not isinstance(sources_data, list):
        raise ConfigError("[[sources]] entries must be an array of tables")

    driver = str(display_data.get("driver", "text")).strip()
    if driver not in {"text", "waveshare_2in13_v4"}:
        raise ConfigError(f"unsupported display driver {driver!r}")

    display = DisplayConfig(
        driver=driver,
        width=_positive_int(display_data.get("width", 40), "display.width"),
        lines=_positive_int(display_data.get("lines", 12), "display.lines"),
        refresh_seconds=_positive_float(
            display_data.get("refresh_seconds", 2.0),
            "display.refresh_seconds",
        ),
        font_size=_positive_int(display_data.get("font_size", 12), "display.font_size"),
        margin=_positive_int(display_data.get("margin", 4), "display.margin"),
    )
    printer = PrinterConfig(
        prefix_source=bool(printer_data.get("prefix_source", True)),
        timestamp=bool(printer_data.get("timestamp", False)),
    )

    sources: list[SourceConfig] = []
    names: set[str] = set()
    for index, raw in enumerate(sources_data):
        if not isinstance(raw, dict):
            raise ConfigError(f"sources[{index}] must be a table")
        name = str(raw.get("name", "")).strip()
        source_type = str(raw.get("type", "")).strip()
        if not name:
            raise ConfigError(f"sources[{index}].name is required")
        if name in names:
            raise ConfigError(f"duplicate source name: {name}")
        if source_type not in {"file", "redis"}:
            raise ConfigError(f"sources[{index}].type must be 'file' or 'redis'")
        if source_type == "file" and not str(raw.get("path", "")).strip():
            raise ConfigError(f"file source {name!r} requires path")
        if source_type == "redis":
            if not str(raw.get("url", "")).strip():
                raise ConfigError(f"redis source {name!r} requires url")
            if not str(raw.get("stream", "")).strip():
                raise ConfigError(f"redis source {name!r} requires stream")

        values = dict(raw)
        values.pop("name", None)
        values.pop("type", None)
        sources.append(SourceConfig(name=name, type=source_type, values=values))
        names.add(name)

    return EpaperConfig(display=display, printer=printer, sources=tuple(sources))
