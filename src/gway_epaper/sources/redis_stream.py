from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from ..model import FeedItem


class RedisStreamSource:
    """Read a Redis Stream incrementally while tracking a durable cursor."""

    def __init__(
        self,
        name: str,
        *,
        url: str,
        stream: str,
        start: str = "$",
        batch_size: int = 100,
        block_ms: int = 1000,
        cursor_file: str | Path | None = None,
        event_types: tuple[str, ...] = (),
        client: Any | None = None,
    ) -> None:
        if batch_size <= 0:
            raise ValueError("batch_size must be greater than zero")
        if block_ms < 0:
            raise ValueError("block_ms must be non-negative")
        self.name = name
        self.url = url
        self.stream = stream
        self.start = start
        self.batch_size = batch_size
        self.block_ms = block_ms
        self.cursor_file = Path(cursor_file).expanduser() if cursor_file else None
        self.event_types = frozenset(event_types)
        self._client = client
        self._cursor = self._load_cursor() or start
        self._read_cursor = self._cursor
        self._retry_at = 0.0
        self._retry_seconds = 1.0

    @property
    def cursor(self) -> str:
        return self._cursor

    def _redis(self):
        if self._client is None:
            try:
                from redis import Redis
            except ImportError as exc:
                raise RuntimeError(
                    "Redis Stream sources require the 'redis' optional dependency"
                ) from exc
            self._client = Redis.from_url(self.url, decode_responses=True)
        return self._client

    def _load_cursor(self) -> str | None:
        if self.cursor_file is None:
            return None
        try:
            value = self.cursor_file.read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            return None
        return value or None

    def _save_cursor(self, value: str) -> None:
        if self.cursor_file is not None:
            self.cursor_file.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.cursor_file.with_suffix(self.cursor_file.suffix + ".tmp")
            temporary.write_text(value + "\n", encoding="utf-8")
            os.replace(temporary, self.cursor_file)
        self._cursor = value

    def commit_batch(self) -> None:
        """Persist the last ID returned by a successfully ingested read batch."""

        if self._read_cursor != self._cursor:
            self._save_cursor(self._read_cursor)

    def _format_authorization(self, fields: dict[str, Any]) -> str:
        charger = fields.get("charger_id") or "?"
        id_tag = fields.get("id_tag") or "?"
        status = fields.get("status") or "?"
        reason = fields.get("reason")
        text = f"AUTH {charger} {id_tag} {status}"
        if reason:
            text += f" ({reason})"
        return text

    def _to_item(self, entry_id: str, fields: dict[str, Any]) -> FeedItem | None:
        event_type = str(fields.get("type", ""))
        if self.event_types and event_type not in self.event_types:
            return None

        if event_type == "ocpp.authorization":
            text = self._format_authorization(fields)
        else:
            text = event_type or "redis-event"

        metadata: dict[str, Any] = dict(fields)
        for key in ("original", "raw"):
            value = metadata.get(key)
            if isinstance(value, str):
                try:
                    metadata[key] = json.loads(value)
                except json.JSONDecodeError:
                    pass

        return FeedItem(
            source=self.name,
            text=text,
            source_id=entry_id,
            metadata=metadata,
        )

    def read_available(self) -> list[FeedItem]:
        now = time.monotonic()
        if now < self._retry_at:
            return []

        try:
            response = self._redis().xread(
                {self.stream: self._cursor},
                count=self.batch_size,
                block=self.block_ms,
            )
        except (ConnectionError, TimeoutError, OSError):
            self._retry_at = now + self._retry_seconds
            self._retry_seconds = min(self._retry_seconds * 2, 30.0)
            return []

        self._retry_seconds = 1.0
        self._retry_at = 0.0
        items: list[FeedItem] = []
        latest = self._cursor
        for _, entries in response:
            for entry_id, fields in entries:
                latest = str(entry_id)
                item = self._to_item(latest, fields)
                if item is not None:
                    items.append(item)
        self._read_cursor = latest
        return items
