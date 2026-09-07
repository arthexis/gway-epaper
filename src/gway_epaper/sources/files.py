from __future__ import annotations

from pathlib import Path

from ..model import FeedItem


class FileSource:
    """Minimal file reader used by the initial scaffold.

    Durable offsets, rotation handling, and asynchronous following belong to
    Phase 1 in PLAN.md.
    """

    def __init__(self, name: str, path: str | Path, *, start: str = "end") -> None:
        if start not in {"beginning", "end"}:
            raise ValueError("start must be 'beginning' or 'end'")
        self.name = name
        self.path = Path(path).expanduser()
        self.start = start
        self._offset: int | None = None

    def read_available(self) -> list[FeedItem]:
        try:
            size = self.path.stat().st_size
        except FileNotFoundError:
            return []

        if self._offset is None:
            self._offset = size if self.start == "end" else 0

        if size < self._offset:
            self._offset = 0

        items: list[FeedItem] = []
        with self.path.open("r", encoding="utf-8", errors="replace") as stream:
            stream.seek(self._offset)
            for line in stream:
                items.append(
                    FeedItem(source=self.name, text=line.rstrip("\r\n"))
                )
            self._offset = stream.tell()
        return items
