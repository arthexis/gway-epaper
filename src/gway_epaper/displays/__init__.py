from __future__ import annotations

from ..config import DisplayConfig
from ..display import TextDisplay
from .waveshare_2in13_v4 import Waveshare2in13V4Display


def build_display(config: DisplayConfig):
    if config.driver == "text":
        return TextDisplay()
    if config.driver == "waveshare_2in13_v4":
        return Waveshare2in13V4Display(
            font_size=config.font_size,
            margin=config.margin,
            min_refresh_seconds=config.min_refresh_seconds,
        )
    raise ValueError(f"unsupported display driver: {config.driver}")


__all__ = ["Waveshare2in13V4Display", "build_display"]
