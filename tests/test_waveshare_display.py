from pathlib import Path

import pytest
from PIL import Image, ImageDraw, ImageFont

import gway_epaper.displays.waveshare_2in13_v4 as waveshare_module
from gway_epaper.config import load_config
from gway_epaper.displays import Waveshare2in13V4Display, build_display


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


class FakeEPD:
    width = 122
    height = 250

    def __init__(self) -> None:
        self.init_calls = 0
        self.displayed_sizes: list[tuple[int, int]] = []
        self.clear_calls: list[int] = []
        self.sleep_calls = 0

    def init(self) -> None:
        self.init_calls += 1

    def getbuffer(self, image):
        self.displayed_sizes.append(image.size)
        return image

    def display(self, _buffer) -> None:
        pass

    def Clear(self, value: int) -> None:
        self.clear_calls.append(value)

    def sleep(self) -> None:
        self.sleep_calls += 1


class FakeEPDModule:
    def __init__(self, epd: FakeEPD) -> None:
        self.epd = epd

    def EPD(self) -> FakeEPD:
        return self.epd


def build_fake_display(*, clock: FakeClock, min_refresh_seconds: float = 5.0):
    epd = FakeEPD()
    display = Waveshare2in13V4Display(
        min_refresh_seconds=min_refresh_seconds,
        clock=clock,
    )
    display._modules = (
        FakeEPDModule(epd),
        Image,
        ImageDraw,
        ImageFont,
    )
    return display, epd


def test_waveshare_v4_configuration_builds_without_loading_hardware(
    tmp_path: Path,
) -> None:
    path = tmp_path / "epaper.toml"
    path.write_text(
        """
[display]
driver = "waveshare_2in13_v4"
font_size = 14
margin = 0
min_refresh_seconds = 7.5
""",
        encoding="utf-8",
    )

    config = load_config(path)
    display = build_display(config.display)

    assert isinstance(display, Waveshare2in13V4Display)
    assert display.font_size == 14
    assert display.margin == 0
    assert display.min_refresh_seconds == 7.5
    assert display._epd is None


def test_render_uses_landscape_buffer_and_skips_unchanged_frame() -> None:
    clock = FakeClock()
    display, epd = build_fake_display(clock=clock)

    assert display.render(["first"]) is True
    assert epd.init_calls == 1
    assert epd.displayed_sizes == [(250, 122)]

    clock.now = 10.0
    assert display.render(["first"]) is False
    assert epd.displayed_sizes == [(250, 122)]


def test_changed_frames_are_coalesced_until_refresh_is_due() -> None:
    clock = FakeClock()
    display, epd = build_fake_display(clock=clock, min_refresh_seconds=5.0)

    assert display.render(["one"]) is True

    clock.now = 1.0
    assert display.render(["two"]) is False
    clock.now = 2.0
    assert display.render(["three"]) is False
    assert len(epd.displayed_sizes) == 1

    clock.now = 5.0
    assert display.render(["three"]) is True
    assert len(epd.displayed_sizes) == 2
    assert display._last_rows == ("three",)


def test_font_aware_wrap_uses_measured_pixel_width() -> None:
    image = Image.new("1", (250, 122), 255)
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype("DejaVuSansMono.ttf", 12)
    max_width = int(Waveshare2in13V4Display._text_width(draw, "wide words", font) - 1)

    rows = Waveshare2in13V4Display._wrap_rows(
        draw,
        ["wide words fit according to the active font"],
        font,
        max_width,
    )

    assert len(rows) > 1
    assert " ".join(rows) == "wide words fit according to the active font"
    assert all(
        Waveshare2in13V4Display._text_width(draw, row, font) <= max_width
        for row in rows
    )


def test_font_aware_wrap_preserves_explicit_newlines() -> None:
    image = Image.new("1", (250, 122), 255)
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype("DejaVuSansMono.ttf", 12)

    rows = Waveshare2in13V4Display._wrap_rows(
        draw,
        ["first line\nsecond line"],
        font,
        240,
    )

    assert rows == ("first line", "second line")


def test_font_aware_wrap_splits_oversized_tokens() -> None:
    image = Image.new("1", (250, 122), 255)
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype("DejaVuSansMono.ttf", 12)
    max_width = int(Waveshare2in13V4Display._text_width(draw, "04A1B2", font))

    rows = Waveshare2in13V4Display._wrap_rows(
        draw,
        ["04A1B2C3D4E5F6"],
        font,
        max_width,
    )

    assert "".join(rows) == "04A1B2C3D4E5F6"
    assert len(rows) > 1
    assert all(
        Waveshare2in13V4Display._text_width(draw, row, font) <= max_width
        for row in rows
    )


def test_clear_uses_hardware_clear_and_resets_cached_frame() -> None:
    clock = FakeClock()
    display, epd = build_fake_display(clock=clock)

    display.render(["one"])
    clock.now = 1.0

    assert display.clear() is True
    assert epd.clear_calls == [0xFF]
    assert display._last_rows == ()
    assert display._pending_rows is None
    assert display._last_refresh_at == 1.0


def test_close_sleeps_initialized_panel_and_allows_reinitialization() -> None:
    clock = FakeClock()
    display, epd = build_fake_display(clock=clock, min_refresh_seconds=0)

    display.render(["one"])
    display.close()
    assert epd.sleep_calls == 1
    assert display._epd is None

    clock.now = 1.0
    display.render(["two"])
    assert epd.init_calls == 2


def test_gpiozero_import_failure_is_reported_as_hardware_access(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeBadPinFactory(ImportError):
        pass

    FakeBadPinFactory.__module__ = "gpiozero.exc"

    def fail_import(_name: str):
        raise FakeBadPinFactory("Unable to load any default pin factory!")

    monkeypatch.setattr(waveshare_module, "import_module", fail_import)

    display = Waveshare2in13V4Display()
    with pytest.raises(RuntimeError) as exc_info:
        display._load()

    message = str(exc_info.value)
    assert "GPIO initialization failed" in message
    assert "hardware-access/permissions" in message
    assert "missing 'required Python module'" not in message
