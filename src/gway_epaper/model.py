from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class FeedItem:
    source: str
    text: str
    observed_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    source_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
