from __future__ import annotations

import time
from collections.abc import Mapping
from queue import Empty
from typing import Any

from ..model import FeedItem


class CeleryQueueSource:
    """Consume display events from a dedicated Celery/Kombu broker queue."""

    def __init__(
        self,
        name: str,
        *,
        url: str,
        queue: str,
        event_types: tuple[str, ...] = (),
        batch_size: int = 100,
        block_seconds: float = 1.0,
        queue_client: Any | None = None,
        clock=time.monotonic,
    ) -> None:
        if not url.strip():
            raise ValueError("url must not be empty")
        if not queue.strip():
            raise ValueError("queue must not be empty")
        if batch_size <= 0:
            raise ValueError("batch_size must be greater than zero")
        if block_seconds < 0:
            raise ValueError("block_seconds must be non-negative")

        self.name = name
        self.url = url
        self.queue_name = queue
        self.event_types = frozenset(event_types)
        self.batch_size = batch_size
        self.block_seconds = block_seconds
        self._queue = queue_client
        self._connection = None
        self._clock = clock
        self._pending: list[Any] = []
        self._retry_at = 0.0
        self._retry_seconds = 1.0

    def _client(self):
        if self._queue is None:
            try:
                from kombu import Connection
            except ImportError as exc:
                raise RuntimeError(
                    "Celery queue sources require the 'celery' optional dependency"
                ) from exc

            self._connection = Connection(self.url)
            self._connection.connect()
            self._queue = self._connection.SimpleQueue(self.queue_name)
        return self._queue

    @staticmethod
    def _format_authorization(fields: Mapping[str, Any]) -> str:
        charger = fields.get("charger_id") or "?"
        id_tag = fields.get("id_tag") or "?"
        status = fields.get("status") or "?"
        return f"AUTH {charger} {id_tag} {status}"

    def _to_item(self, fields: Mapping[str, Any]) -> FeedItem | None:
        event_type = str(fields.get("type", ""))
        if self.event_types and event_type not in self.event_types:
            return None

        if event_type == "ocpp.authorization":
            text = self._format_authorization(fields)
        else:
            text = event_type or "queue-event"

        return FeedItem(
            source=self.name,
            text=text,
            source_id=str(fields.get("event_id", "")) or None,
            metadata=dict(fields),
        )

    def _get_message(self, *, block: bool, timeout: float | None = None):
        queue = self._client()
        if block:
            return queue.get(block=True, timeout=timeout)
        return queue.get(block=False)

    def read_available(
        self, *, block_seconds: float | None = None
    ) -> list[FeedItem]:
        """Read one bounded batch, deferring acknowledgements until commit_batch."""

        effective_block = (
            self.block_seconds if block_seconds is None else block_seconds
        )
        if effective_block < 0:
            raise ValueError("block_seconds must be non-negative")

        now = self._clock()
        if now < self._retry_at:
            return []

        items: list[FeedItem] = []
        try:
            for index in range(self.batch_size):
                try:
                    message = self._get_message(
                        block=index == 0 and effective_block > 0,
                        timeout=effective_block if index == 0 else None,
                    )
                except Empty:
                    break

                payload = message.payload
                if not isinstance(payload, Mapping):
                    message.ack()
                    continue

                item = self._to_item(payload)
                if item is None:
                    message.ack()
                    continue

                self._pending.append(message)
                items.append(item)
        except (ConnectionError, TimeoutError, OSError):
            self._retry_at = now + self._retry_seconds
            self._retry_seconds = min(self._retry_seconds * 2, 30.0)
            self.close()
            return []

        self._retry_at = 0.0
        self._retry_seconds = 1.0
        return items

    def commit_batch(self) -> None:
        """Acknowledge messages only after the runtime has ingested their items."""

        pending, self._pending = self._pending, []
        for message in pending:
            message.ack()

    def close(self) -> None:
        queue, self._queue = self._queue, None
        if queue is not None:
            close = getattr(queue, "close", None)
            if close is not None:
                close()
        connection, self._connection = self._connection, None
        if connection is not None:
            connection.release()
