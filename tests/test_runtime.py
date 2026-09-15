from gway_epaper.runtime import Runtime


class FakePrinter:
    def __init__(self, *, dirty=False, rows=()) -> None:
        self.items = []
        self.dirty = dirty
        self.rows = tuple(rows)
        self.clean_calls = 0

    def append(self, item) -> None:
        self.items.append(item)
        self.dirty = True

    def snapshot(self):
        return self.rows

    def mark_clean(self):
        self.clean_calls += 1
        self.dirty = False


class FakeRedisSource:
    def __init__(self, name: str) -> None:
        self.name = name
        self.read_blocks: list[int | None] = []
        self.commits = 0

    def read_available(self, *, block_ms: int | None = None):
        self.read_blocks.append(block_ms)
        return []

    def commit_batch(self) -> None:
        self.commits += 1


class FakeDisplay:
    def __init__(self):
        self.frames = []

    def render(self, rows):
        self.frames.append(tuple(rows))
        return True


def test_redis_polling_allows_only_one_blocking_source_and_rotates_fairly() -> None:
    first = FakeRedisSource("first")
    second = FakeRedisSource("second")
    third = FakeRedisSource("third")
    runtime = Runtime.__new__(Runtime)
    runtime.redis_sources = [first, second, third]
    runtime.printer = FakePrinter()
    runtime._redis_blocking_index = 0
    runtime._poll_redis_sources()
    assert first.read_blocks == [None]
    assert second.read_blocks == [0]
    assert third.read_blocks == [0]
    assert [first.commits, second.commits, third.commits] == [1, 1, 1]
    runtime._poll_redis_sources()
    assert first.read_blocks == [None, 0]
    assert second.read_blocks == [0, None]
    assert third.read_blocks == [0, 0]
    runtime._poll_redis_sources()
    assert first.read_blocks == [None, 0, 0]
    assert second.read_blocks == [0, None, 0]
    assert third.read_blocks == [0, 0, None]


def test_poll_does_not_redraw_clean_restored_frame() -> None:
    runtime = Runtime.__new__(Runtime)
    runtime.file_sources = []
    runtime.redis_sources = []
    runtime.celery_sources = []
    runtime.printer = FakePrinter(dirty=False, rows=("A", "B", "C"))
    runtime.display = FakeDisplay()
    assert runtime.poll_once() is False
    assert runtime.display.frames == []


def test_dirty_frame_renders_and_becomes_clean() -> None:
    runtime = Runtime.__new__(Runtime)
    runtime.file_sources = []
    runtime.redis_sources = []
    runtime.celery_sources = []
    runtime.printer = FakePrinter(dirty=True, rows=("A", "B", "C", "D"))
    runtime.display = FakeDisplay()
    assert runtime.poll_once() is True
    assert runtime.display.frames == [("A", "B", "C", "D")]
    assert runtime.printer.clean_calls == 1
