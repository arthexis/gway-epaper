from __future__ import annotations

import sys
from pathlib import Path

from .runtime import run_forever


def main(argv: list[str] | None = None) -> int:
    """Internal foreground entry point used by the packaged systemd unit."""

    arguments = list(sys.argv[1:] if argv is None else argv)
    if len(arguments) != 1:
        raise SystemExit("usage: python -m gway_epaper.service CONFIG")
    run_forever(Path(arguments[0]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
