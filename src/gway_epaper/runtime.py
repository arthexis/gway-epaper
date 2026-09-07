from __future__ import annotations

import time
from pathlib import Path

from .config import EpaperConfig, load_config
from .displays import build_display
from .printer import PrinterBuffer
from .sources import FileSource, RedisStreamSource


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
        self.redis_sources = [
            RedisStreamSource(
                source.name,
                url=str(source.values["url"]),
                stream=str(source.values["stream"]),
                start=str(source.values.get("start", "$")),
                batch_size=int(source.values.get("batch_size", 100)),
                block_ms=int(source.values.get("block_ms", 1000)),
                cursor_file=source.values.get("cursor_file"),
                event_types=tuple(source.values.get("event_types", ())),
            )
            for source in config.sources
            if source.type == "redis"
        ]
        self._redis_blocking_index = 0

    def _poll_redis_sources(self) -> None:
        if not self.redis_sources:
            return

        source_count = len(self.redis_sources)
        blocking_index = self._redis_blocking_index % source_count
        order = [
            self.redis_sources[(blocking_index + offset) % source_count]
            for offset in range(source_count)
        ]

        for offset, source in enumerate(order):
            items = source.read_available(block_ms=None if offset == 0 else 0)
            for item in items:
                self.printer.append(item)
            source.commit_batch()

        self._redis_blocking_index = (blocking_index + 1) % source_count

    def poll_once(self):
        for source in self.file_sources:
            for item in source.read_available():
                self.printer.append(item)

        self._poll_redis_sources()

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
