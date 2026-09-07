from __future__ import annotations

import time
from pathlib import Path

from .config import EpaperConfig, load_config
from .displays import build_display
from .printer import PrinterBuffer
from .sources import FileSource


class Runtime:
    def __init__(self, config: EpaperConfig) -> None:
        self.config = config
        self.printer = PrinterBuffer(
            width=config.display.width,
            lines=config.display.lines,
            config=config.printer,
        )
        self.display = build_display(config.display)
        self.file_sources = [
            FileSource(
                source.name,
                source.values["path"],
                start=str(source.values.get("start", "end")),
            )
            for source in config.sources
            if source.type == "file"
        ]

    def poll_once(self):
        for source in self.file_sources:
            for item in source.read_available():
                self.printer.append(item)
        return self.display.render(self.printer.snapshot())

    def close(self) -> None:
        close = getattr(self.display, "close", None)
        if close is not None:
            close()


def build_runtime(path: str | Path = "epaper.toml") -> Runtime:
    return Runtime(load_config(path))


def run_forever(path: str | Path = "epaper.toml") -> None:
    runtime = build_runtime(path)
    try:
        while True:
            frame = runtime.poll_once()
            if isinstance(frame, str) and frame:
                print("\033[2J\033[H" + frame, flush=True)
            time.sleep(runtime.config.display.refresh_seconds)
    finally:
        runtime.close()
