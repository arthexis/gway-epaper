from __future__ import annotations

from collections.abc import Sequence
from importlib import import_module


class Waveshare2in13V4Display:
    """Waveshare 2.13-inch e-Paper HAT V4 backend (250x122 monochrome)."""

    width = 250
    height = 122

    def __init__(self, *, font_size: int = 12, margin: int = 4) -> None:
        self.font_size = font_size
        self.margin = margin
        self._epd = None

    def _load(self):
        try:
            module = import_module("waveshare_epd.epd2in13_V4")
            image_module = import_module("PIL.Image")
            draw_module = import_module("PIL.ImageDraw")
            font_module = import_module("PIL.ImageFont")
        except ImportError as exc:
            raise RuntimeError(
                "Waveshare 2.13 V4 support requires the 'epaper' extra and "
                "Waveshare's waveshare_epd Python package"
            ) from exc
        return module, image_module, draw_module, font_module

    def _device(self):
        if self._epd is None:
            module, _, _, _ = self._load()
            self._epd = module.EPD()
            self._epd.init()
        return self._epd

    def render(self, rows: Sequence[str]) -> None:
        epd = self._device()
        _, image_module, draw_module, font_module = self._load()
        image = image_module.new("1", (epd.height, epd.width), 255)
        draw = draw_module.Draw(image)
        try:
            font = font_module.truetype("DejaVuSansMono.ttf", self.font_size)
        except OSError:
            font = font_module.load_default()

        line_height = self.font_size + 2
        capacity = max(1, (epd.width - 2 * self.margin) // line_height)
        visible = tuple(rows)[-capacity:]
        y = self.margin
        for row in visible:
            draw.text((self.margin, y), row, font=font, fill=0)
            y += line_height

        epd.display(epd.getbuffer(image))

    def close(self) -> None:
        if self._epd is not None:
            self._epd.sleep()
            self._epd = None
