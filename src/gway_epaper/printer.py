from __future__ import annotations

from collections import deque
from textwrap import wrap

from .config import PrinterConfig
from .model import FeedItem


class PrinterBuffer:
    def __init__(
        self,
        *,
        width: int,
        lines: int,
        config: PrinterConfig | None = None,
    ) -> None:
        if width <= 0 or lines <= 0:
            raise ValueError("width and lines must be greater than zero")
        self.width = width
        self.lines = lines
        self.config = config or PrinterConfig()
        self._rows: deque[str] = deque(maxlen=lines)

    def _prefix(self, item: FeedItem) -> str:
        parts: list[str] = []
        if self.config.timestamp:
            parts.append(item.observed_at.astimezone().strftime("%H:%M:%S"))
        if self.config.prefix_source:
            parts.append(item.source)
        return " ".join(parts)

    def append(self, item: FeedItem) -> None:
        prefix = self._prefix(item)
        text = f"{prefix} | {item.text}" if prefix else item.text
        rows = wrap(
            text,
            width=self.width,
            replace_whitespace=False,
            drop_whitespace=False,
        ) or [""]
        self._rows.extend(row[: self.width] for row in rows)

    def snapshot(self) -> tuple[str, ...]:
        return tuple(self._rows)

    def render_text(self) -> str:
        return "\n".join(self._rows)
