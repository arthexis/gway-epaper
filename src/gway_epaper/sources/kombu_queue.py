from __future__ import annotations

import time
from collections.abc import Callable
from queue import Empty
from typing import Any

from kombu import Connection

from ..model import FeedItem


class KombuQueueSource:
    """Consume structured events from a Kombu queue with explicit acknowledgements."""

    def __init__(
        self,
        name: str,
        *,
        url: str,
        queue_name: str,
        batch_size: int = 100,
        block_seconds: float = 1.0,
        event_types: tuple[str, ...] = (),
        connection: Any | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if batch_size <= 0:
            raise ValueError("batch_size must be greater than zero")
        if block_seconds < 0:
            raise ValueError("block_seconds must be non-negative")
        self.name = name
        self.url = url
        self.queue_name = queue_name
        self.batch_size = batch_size
        self.block_seconds = block_seconds
        self.event_types = frozenset(event_types)
        self._connection = connection
        self._queue = None
        self._pending: list[Any] = []
        self._clock = clock
        self._retry_at = 0.0
        self._retry_seconds = 1.0

    def _connect(self):
        if self._connection is None:
            self._connection = Connection(self.url, connect_timeout=1)
            self._connection.ensure_connection(max_retries=0, timeout=1)
        if self._queue is None:
            self._queue = self._connection.SimpleQueue(self.queue_name)
        return self._queue

    @staticmethod
    def _format_authorization(fields: dict[str, Any]) -> str:
        charger = fields.get("charger_id") or "?"
        id_tag = fields.get("id_tag") or "?"
        status = fields.get("status") or "?"
        reason = fields.get("reason")
        text = f"AUTH {charger} {id_tag} {status}"
        if reason:
            text += f" ({reason})"
        return text

    def _to_item(self, fields: dict[str, Any], message: Any) -> FeedItem | None:
        event_type = str(fields.get("type", ""))
        if self.event_types and event_type not in self.event_types:
            return None

        text = (
            self._format_authorization(fields)
            if event_type == "ocpp.authorization"
            else event_type or "queue-event"
        )
        message_id = fields.get("message_id")
        if message_id is None:
            message_id = getattr(message, "delivery_tag", None)
        return FeedItem(
            source=self.name,
            text=text,
            source_id=str(message_id) if message_id is not None else None,
            metadata=dict(fields),
        )

    def _reset_connection(self) -> None:
        queue = self._queue
        connection = self._connection
        self._queue = None
        self._connection = None
        if queue is not None:
            try:
                queue.close()
            except Exception:
                pass
        if connection is not None:
            try:
                connection.release()
            except Exception:
                pass

    def read_available(self) -> list[FeedItem]:
        """Read one bounded batch without acknowledging it yet."""

        if self._pending:
            return []
        now = self._clock()
        if now < self._retry_at:
            return []

        try:
            queue = self._connect()
            messages: list[Any] = []
            for index in range(self.batch_size):
                try:
                    message = queue.get(
                        block=index == 0 and self.block_seconds > 0,
                        timeout=self.block_seconds if index == 0 and self.block_seconds > 0 else None,
                    )
                except Empty:
                    break
                messages.append(message)
        except (ConnectionError, TimeoutError, OSError):
            self._reset_connection()
            self._retry_at = now + self._retry_seconds
            self._retry_seconds = min(self._retry_seconds * 2, 30.0)
            return []

        self._retry_at = 0.0
        self._retry_seconds = 1.0
        self._pending = messages
        items: list[FeedItem] = []
        for message in messages:
            payload = message.payload
            if not isinstance(payload, dict):
                continue
            item = self._to_item(payload, message)
            if item is not None:
                items.append(item)
        return items

    def commit_batch(self) -> None:
        """Acknowledge all messages from the last successfully ingested batch."""

        pending, self._pending = self._pending, []
        for message in pending:
            message.ack()

    def close(self) -> None:
        self._reset_connection()
