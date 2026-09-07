from __future__ import annotations

from collections.abc import Sequence


class TextDisplay:
    """Development display backend used before hardware drivers land."""

    def render(self, rows: Sequence[str]) -> str:
        return "\n".join(rows)
