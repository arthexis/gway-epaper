from __future__ import annotations

import json
import os
from pathlib import Path

from ..model import FeedItem


class FileSource:
    """Follow a text file with durable, commit-after-ingest cursor state."""

    def __init__(
        self,
        name: str,
        path: str | Path,
        *,
        start: str = "end",
        cursor_file: str | Path | None = None,
        max_bytes: int = 65536,
    ) -> None:
        if start not in {"beginning", "end"}:
            raise ValueError("start must be 'beginning' or 'end'")
        if max_bytes <= 0:
            raise ValueError("max_bytes must be greater than zero")
        if isinstance(cursor_file, str) and not cursor_file.strip():
            raise ValueError("cursor_file must not be empty")

        self.name = name
        self.path = Path(path).expanduser()
        self.start = start
        self.cursor_file = (
            Path(cursor_file).expanduser() if cursor_file is not None else None
        )
        self.max_bytes = max_bytes

        self._identity: tuple[int, int] | None = None
        self._committed_offset: int | None = None
        self._read_offset: int | None = None
        self._scan_offset: int | None = None
        self._partial = b""
        self._load_state()

    @staticmethod
    def _identity_for(stat_result) -> tuple[int, int]:
        return int(stat_result.st_dev), int(stat_result.st_ino)

    def _load_state(self) -> None:
        if self.cursor_file is None:
            return
        try:
            raw = json.loads(self.cursor_file.read_text(encoding="utf-8"))
            identity = (int(raw["device"]), int(raw["inode"]))
            offset = int(raw["offset"])
        except FileNotFoundError:
            return
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            return
        if offset < 0:
            return
        self._identity = identity
        self._committed_offset = offset
        self._read_offset = offset
        self._scan_offset = offset

    def _save_state(self, identity: tuple[int, int], offset: int) -> None:
        if self.cursor_file is not None:
            self.cursor_file.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.cursor_file.with_suffix(self.cursor_file.suffix + ".tmp")
            temporary.write_text(
                json.dumps(
                    {"device": identity[0], "inode": identity[1], "offset": offset},
                    separators=(",", ":"),
                )
                + "\n",
                encoding="utf-8",
            )
            os.replace(temporary, self.cursor_file)
        self._committed_offset = offset

    def _reset(self, identity: tuple[int, int], offset: int) -> None:
        self._identity = identity
        self._read_offset = offset
        self._scan_offset = offset
        self._partial = b""

    def _prepare(self, stat_result) -> None:
        identity = self._identity_for(stat_result)
        size = int(stat_result.st_size)

        if self._identity is None:
            self._reset(identity, size if self.start == "end" else 0)
            return

        if identity != self._identity:
            self._reset(identity, 0)
            return

        assert self._read_offset is not None
        if size < self._read_offset:
            self._reset(identity, 0)
            return

        assert self._scan_offset is not None
        if size < self._scan_offset:
            self._reset(identity, 0)

    def read_available(self) -> list[FeedItem]:
        try:
            stat_result = self.path.stat()
        except FileNotFoundError:
            return []

        self._prepare(stat_result)
        assert self._identity is not None
        assert self._read_offset is not None
        assert self._scan_offset is not None

        with self.path.open("rb") as stream:
            stream.seek(self._scan_offset)
            chunk = stream.read(self.max_bytes)

        if not chunk:
            return []

        self._scan_offset += len(chunk)
        data = self._partial + chunk
        parts = data.splitlines(keepends=True)
        self._partial = b""

        if parts and not parts[-1].endswith((b"\n", b"\r")):
            self._partial = parts.pop()

        items: list[FeedItem] = []
        complete_bytes = 0
        for part in parts:
            complete_bytes += len(part)
            text = part.rstrip(b"\r\n").decode("utf-8", errors="replace")
            end_offset = self._read_offset + complete_bytes
            items.append(
                FeedItem(
                    source=self.name,
                    text=text,
                    source_id=f"{self._identity[0]}:{self._identity[1]}:{end_offset}",
                )
            )

        if complete_bytes:
            self._read_offset += complete_bytes
        return items

    def commit_batch(self) -> None:
        """Persist the last complete line accepted by the printer."""

        if self._identity is None or self._read_offset is None:
            return
        if self._read_offset != self._committed_offset:
            self._save_state(self._identity, self._read_offset)
