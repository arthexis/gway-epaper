from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

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
        self.sleep_calls = 0

    def init(self) -> None:
        self.init_calls += 1

    def getbuffer(self, image):
        self.displayed_sizes.append(image.size)
        return image

    def display(self, _buffer) -> None:
        pass

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
