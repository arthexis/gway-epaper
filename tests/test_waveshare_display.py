from pathlib import Path

from gway_epaper.config import load_config
from gway_epaper.displays import Waveshare2in13V4Display, build_display


def test_waveshare_v4_configuration_builds_without_loading_hardware(tmp_path: Path) -> None:
    path = tmp_path / "epaper.toml"
    path.write_text(
        """
[display]
driver = "waveshare_2in13_v4"
font_size = 14
margin = 5
""",
        encoding="utf-8",
    )

    config = load_config(path)
    display = build_display(config.display)

    assert isinstance(display, Waveshare2in13V4Display)
    assert display.font_size == 14
    assert display.margin == 5
    assert display._epd is None
