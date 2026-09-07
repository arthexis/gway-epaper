import json
from pathlib import Path

import pytest

from gway_epaper.config import ConfigError, load_config
from gway_epaper.sources.files import FileSource


def texts(items):
    return [item.text for item in items]


def test_cursor_is_committed_only_after_batch_acceptance(tmp_path: Path) -> None:
    log = tmp_path / "events.log"
    cursor = tmp_path / "events.cursor"
    log.write_text("one\ntwo\n", encoding="utf-8")
    source = FileSource(
        "log",
        log,
        start="beginning",
        cursor_file=cursor,
    )

    assert texts(source.read_available()) == ["one", "two"]
    assert not cursor.exists()

    source.commit_batch()

    state = json.loads(cursor.read_text(encoding="utf-8"))
    assert state["offset"] == len(b"one\ntwo\n")


def test_restart_resumes_after_last_committed_line(tmp_path: Path) -> None:
    log = tmp_path / "events.log"
    cursor = tmp_path / "events.cursor"
    log.write_text("one\ntwo\n", encoding="utf-8")

    first = FileSource("log", log, start="beginning", cursor_file=cursor)
    assert texts(first.read_available()) == ["one", "two"]
    first.commit_batch()

    with log.open("a", encoding="utf-8") as stream:
        stream.write("three\n")

    restarted = FileSource("log", log, start="beginning", cursor_file=cursor)
    assert texts(restarted.read_available()) == ["three"]


def test_partial_line_is_not_emitted_or_committed_until_complete(
    tmp_path: Path,
) -> None:
    log = tmp_path / "events.log"
    cursor = tmp_path / "events.cursor"
    log.write_bytes(b"complete\npart")
    source = FileSource(
        "log",
        log,
        start="beginning",
        cursor_file=cursor,
        max_bytes=64,
    )

    assert texts(source.read_available()) == ["complete"]
    source.commit_batch()
    assert json.loads(cursor.read_text(encoding="utf-8"))["offset"] == len(
        b"complete\n"
    )

    with log.open("ab") as stream:
        stream.write(b"ial\n")

    assert texts(source.read_available()) == ["partial"]
    source.commit_batch()
    assert json.loads(cursor.read_text(encoding="utf-8"))["offset"] == len(
        b"complete\npartial\n"
    )


def test_reads_are_bounded_without_losing_long_partial_lines(tmp_path: Path) -> None:
    log = tmp_path / "events.log"
    log.write_bytes(b"abcdefghij\nnext\n")
    source = FileSource("log", log, start="beginning", max_bytes=4)

    assert source.read_available() == []
    assert source.read_available() == []
    assert texts(source.read_available()) == ["abcdefghij"]
    assert texts(source.read_available()) == ["next"]


def test_truncation_restarts_from_beginning(tmp_path: Path) -> None:
    log = tmp_path / "events.log"
    cursor = tmp_path / "events.cursor"
    log.write_text("old-one\nold-two\n", encoding="utf-8")
    source = FileSource("log", log, start="beginning", cursor_file=cursor)
    source.read_available()
    source.commit_batch()

    log.write_text("new\n", encoding="utf-8")

    assert texts(source.read_available()) == ["new"]


def test_rename_and_recreate_rotation_reads_new_file_from_start(tmp_path: Path) -> None:
    log = tmp_path / "events.log"
    rotated = tmp_path / "events.log.1"
    cursor = tmp_path / "events.cursor"
    log.write_text("old\n", encoding="utf-8")
    source = FileSource("log", log, start="beginning", cursor_file=cursor)
    source.read_available()
    source.commit_batch()

    log.rename(rotated)
    log.write_text("new-one\nnew-two\n", encoding="utf-8")

    assert texts(source.read_available()) == ["new-one", "new-two"]


def test_missing_file_can_reappear(tmp_path: Path) -> None:
    log = tmp_path / "events.log"
    source = FileSource("log", log, start="beginning")

    assert source.read_available() == []
    log.write_text("hello\n", encoding="utf-8")
    assert texts(source.read_available()) == ["hello"]


def test_start_end_skips_existing_content_but_reads_appends(tmp_path: Path) -> None:
    log = tmp_path / "events.log"
    log.write_text("existing\n", encoding="utf-8")
    source = FileSource("log", log, start="end")

    assert source.read_available() == []
    with log.open("a", encoding="utf-8") as stream:
        stream.write("new\n")
    assert texts(source.read_available()) == ["new"]


def test_config_rejects_empty_file_cursor_and_zero_max_bytes(tmp_path: Path) -> None:
    path = tmp_path / "epaper.toml"
    path.write_text(
        """
[[sources]]
name = "log"
type = "file"
path = "/tmp/events.log"
cursor_file = ""
max_bytes = 0
""",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="max_bytes must be greater than zero"):
        load_config(path)

    path.write_text(
        """
[[sources]]
name = "log"
type = "file"
path = "/tmp/events.log"
cursor_file = ""
max_bytes = 1024
""",
        encoding="utf-8",
    )
    with pytest.raises(ConfigError, match="cursor_file must not be empty"):
        load_config(path)
