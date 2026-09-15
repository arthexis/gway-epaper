from __future__ import annotations

import json
import os
import tempfile
from collections import deque
from pathlib import Path
from textwrap import wrap

from .config import PrinterConfig
from .model import FeedItem


class PrinterBuffer:
    def __init__(self, *, width: int, lines: int, config: PrinterConfig | None = None) -> None:
        if width <= 0 or lines <= 0:
            raise ValueError("width and lines must be greater than zero")
        self.width = width
        self.lines = lines
        self.config = config or PrinterConfig()
        self.state_file = Path(self.config.state_file).expanduser() if self.config.state_file else None
        self._rows: deque[str] = deque(maxlen=lines)
        self._dirty = False
        self._restore()

    @property
    def dirty(self) -> bool:
        return self._dirty

    def mark_clean(self) -> None:
        self._dirty = False

    def _restore(self) -> None:
        if self.state_file is None:
            return
        try:
            payload = json.loads(self.state_file.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            return
        rows = payload.get("rows") if isinstance(payload, dict) else None
        if not isinstance(rows, list) or not all(isinstance(row, str) for row in rows):
            return
        self._rows.extend(rows[-self.lines :])
        # Restored rows describe the image the e-paper panel is expected to retain.
        # They are deliberately clean so process startup does not refresh the panel.
        self._dirty = False

    def _persist(self) -> None:
        if self.state_file is None:
            return
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps({"version": 1, "rows": list(self._rows)}, ensure_ascii=False)
        descriptor, temporary = tempfile.mkstemp(
            prefix=f".{self.state_file.name}.", dir=self.state_file.parent, text=True
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                stream.write(payload)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.state_file)
        finally:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass

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
        rows = wrap(text, width=self.width, replace_whitespace=False, drop_whitespace=False) or [""]
        self._rows.extend(row[: self.width] for row in rows)
        self._persist()
        self._dirty = True

    def snapshot(self) -> tuple[str, ...]:
        return tuple(self._rows)

    def render_text(self) -> str:
        return "\n".join(self._rows)
