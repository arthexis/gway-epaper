from gway_epaper.config import PrinterConfig
from gway_epaper.model import FeedItem
from gway_epaper.printer import PrinterBuffer


def test_new_lines_append_at_bottom_and_old_lines_scroll_up() -> None:
    printer = PrinterBuffer(
        width=20,
        lines=3,
        config=PrinterConfig(prefix_source=False),
    )

    for value in ("one", "two", "three", "four"):
        printer.append(FeedItem(source="test", text=value))

    assert printer.snapshot() == ("two", "three", "four")


def test_wrapped_rows_participate_in_scroll_capacity() -> None:
    printer = PrinterBuffer(
        width=5,
        lines=3,
        config=PrinterConfig(prefix_source=False),
    )

    printer.append(FeedItem(source="test", text="1234567890"))
    printer.append(FeedItem(source="test", text="abcde"))

    assert printer.snapshot() == ("12345", "67890", "abcde")
