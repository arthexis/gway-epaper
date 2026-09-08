from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from importlib import import_module


class Waveshare2in13V4Display:
    """Waveshare 2.13-inch e-Paper HAT V4 backend (250x122 monochrome)."""

    width = 250
    height = 122

    def __init__(
        self,
        *,
        font_size: int = 12,
        margin: int = 4,
        min_refresh_seconds: float = 5.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if min_refresh_seconds < 0:
            raise ValueError("min_refresh_seconds must be non-negative")
        self.font_size = font_size
        self.margin = margin
        self.min_refresh_seconds = min_refresh_seconds
        self._clock = clock
        self._epd = None
        self._modules = None
        self._last_rows: tuple[str, ...] | None = None
        self._pending_rows: tuple[str, ...] | None = None
        self._last_refresh_at: float | None = None

    def _load(self):
        if self._modules is not None:
            return self._modules
        try:
            module = import_module("waveshare_epd.epd2in13_V4")
            image_module = import_module("PIL.Image")
            draw_module = import_module("PIL.ImageDraw")
            font_module = import_module("PIL.ImageFont")
        except Exception as exc:
            # Waveshare constructs gpiozero devices while epdconfig is imported.
            # BadPinFactory is ImportError-compatible, so it must be identified
            # before treating ImportError as a missing Python dependency.
            if exc.__class__.__module__.startswith("gpiozero"):
                raise RuntimeError(
                    "Waveshare GPIO initialization failed before the display driver "
                    "could load. gpiozero could not access a usable Raspberry Pi GPIO "
                    "backend. Check that /dev/gpiochip* or /dev/gpiomem exists and is "
                    "accessible to the user running gway, and that SPI is enabled and "
                    "/dev/spidev* is accessible. This is a hardware-access/permissions "
                    "problem, not a missing waveshare-epd dependency. "
                    f"Original error: {exc}"
                ) from exc
            if isinstance(exc, ImportError):
                missing = getattr(exc, "name", None) or "required Python module"
                raise RuntimeError(
                    f"Waveshare 2.13 V4 support is missing {missing!r}. "
                    "On Raspberry Pi Linux, gway-epaper installs waveshare-epd, "
                    "spidev, gpiozero, and lgpio automatically. Run "
                    "'sudo gway upgrade epaper --force'. If pip cannot build/install "
                    "a dependency, install Raspberry Pi OS prerequisites with "
                    "'sudo apt install git build-essential python3-dev', ensure SPI "
                    "is enabled in raspi-config, then run the Gway upgrade again."
                ) from exc
            raise
        self._modules = module, image_module, draw_module, font_module
        return self._modules

    def _device(self):
        if self._epd is None:
            module, _, _, _ = self._load()
            self._epd = module.EPD()
            self._epd.init()
        return self._epd

    def _refresh_due(self, now: float) -> bool:
        return (
            self._last_refresh_at is None
            or now - self._last_refresh_at >= self.min_refresh_seconds
        )

    def render(self, rows: Sequence[str]) -> bool:
        requested = tuple(rows)
        if requested == self._last_rows and self._pending_rows is None:
            return False

        self._pending_rows = requested
        now = self._clock()
        if not self._refresh_due(now):
            return False

        visible_rows = self._pending_rows
        epd = self._device()
        _, image_module, draw_module, font_module = self._load()

        # Waveshare exposes the panel in portrait coordinates (122x250). The
        # application renders landscape, so the Pillow image is intentionally
        # created as (epd.height, epd.width) == (250, 122).
        image = image_module.new("1", (epd.height, epd.width), 255)
        draw = draw_module.Draw(image)
        try:
            font = font_module.truetype("DejaVuSansMono.ttf", self.font_size)
        except OSError:
            font = font_module.load_default()

        line_height = self.font_size + 2
        capacity = max(1, (epd.width - 2 * self.margin) // line_height)
        visible = visible_rows[-capacity:]
        y = self.margin
        for row in visible:
            draw.text((self.margin, y), row, font=font, fill=0)
            y += line_height

        epd.display(epd.getbuffer(image))
        self._last_rows = visible_rows
        self._pending_rows = None
        self._last_refresh_at = now
        return True

    def clear(self) -> bool:
        """Immediately clear the physical panel, bypassing refresh coalescing."""

        epd = self._device()
        epd.Clear(0xFF)
        self._last_rows = ()
        self._pending_rows = None
        self._last_refresh_at = self._clock()
        return True

    def close(self) -> None:
        if self._epd is not None:
            self._epd.sleep()
            self._epd = None
