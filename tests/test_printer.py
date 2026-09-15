import json

from gway_epaper.config import PrinterConfig
from gway_epaper.model import FeedItem
from gway_epaper.printer import PrinterBuffer


def config(state_file=None):
    return PrinterConfig(prefix_source=False, state_file=state_file)


def test_new_lines_append_at_bottom_and_old_lines_scroll_up() -> None:
    printer = PrinterBuffer(width=20, lines=3, config=config(False))
    for value in ("one", "two", "three", "four"):
        printer.append(FeedItem(source="test", text=value))
    assert printer.snapshot() == ("two", "three", "four")


def test_wrapped_rows_participate_in_scroll_capacity() -> None:
    printer = PrinterBuffer(width=5, lines=3, config=config(False))
    printer.append(FeedItem(source="test", text="1234567890"))
    printer.append(FeedItem(source="test", text="abcde"))
    assert printer.snapshot() == ("12345", "67890", "abcde")


def test_frame_is_restored_and_append_continues_after_restart(tmp_path) -> None:
    state = tmp_path / "frame.json"
    first = PrinterBuffer(width=20, lines=4, config=config(str(state)))
    for value in ("A", "B", "C"):
        first.append(FeedItem(source="test", text=value))
    assert first.snapshot() == ("A", "B", "C")
    assert first.dirty is True

    restarted = PrinterBuffer(width=20, lines=4, config=config(str(state)))
    assert restarted.snapshot() == ("A", "B", "C")
    assert restarted.dirty is False

    restarted.append(FeedItem(source="test", text="D"))
    assert restarted.snapshot() == ("A", "B", "C", "D")
    assert restarted.dirty is True
    assert json.loads(state.read_text(encoding="utf-8"))["rows"] == ["A", "B", "C", "D"]


def test_restore_keeps_only_current_capacity(tmp_path) -> None:
    state = tmp_path / "frame.json"
    state.write_text(json.dumps({"version": 1, "rows": ["A", "B", "C", "D"]}), encoding="utf-8")
    printer = PrinterBuffer(width=20, lines=2, config=config(str(state)))
    assert printer.snapshot() == ("C", "D")
    assert printer.dirty is False


def test_corrupt_state_is_ignored_without_forcing_redraw(tmp_path) -> None:
    state = tmp_path / "frame.json"
    state.write_text("not json", encoding="utf-8")
    printer = PrinterBuffer(width=20, lines=4, config=config(str(state)))
    assert printer.snapshot() == ()
    assert printer.dirty is False
