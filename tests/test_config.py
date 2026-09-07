from pathlib import Path

import pytest

from gway_epaper.config import ConfigError, load_config


def test_load_config_accepts_file_and_redis_sources(tmp_path: Path) -> None:
    path = tmp_path / "epaper.toml"
    path.write_text(
        """
[display]
driver = "text"
width = 32
lines = 8

[[sources]]
name = "log"
type = "file"
path = "/tmp/example.log"

[[sources]]
name = "auth"
type = "redis"
url = "redis://localhost:6379/0"
stream = "arthexis:events"
event_types = ["ocpp.authorization"]
batch_size = 50
block_ms = 250
""",
        encoding="utf-8",
    )

    config = load_config(path)

    assert config.display.width == 32
    assert config.display.lines == 8
    assert [source.type for source in config.sources] == ["file", "redis"]


def test_load_config_rejects_duplicate_source_names(tmp_path: Path) -> None:
    path = tmp_path / "epaper.toml"
    path.write_text(
        """
[[sources]]
name = "same"
type = "file"
path = "/tmp/a"

[[sources]]
name = "same"
type = "file"
path = "/tmp/b"
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="duplicate source name"):
        load_config(path)


def test_load_config_rejects_invalid_redis_event_types(tmp_path: Path) -> None:
    path = tmp_path / "epaper.toml"
    path.write_text(
        """
[[sources]]
name = "auth"
type = "redis"
url = "redis://localhost:6379/0"
stream = "arthexis:events"
event_types = "ocpp.authorization"
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="event_types must be an array of strings"):
        load_config(path)


def test_load_config_rejects_zero_redis_batch_size(tmp_path: Path) -> None:
    path = tmp_path / "epaper.toml"
    path.write_text(
        """
[[sources]]
name = "auth"
type = "redis"
url = "redis://localhost:6379/0"
stream = "arthexis:events"
batch_size = 0
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="batch_size must be greater than zero"):
        load_config(path)
