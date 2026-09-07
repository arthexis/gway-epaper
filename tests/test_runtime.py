from gway_epaper.runtime import Runtime


class FakePrinter:
    def __init__(self) -> None:
        self.items = []

    def append(self, item) -> None:
        self.items.append(item)


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
    assert [first.commits, second.commits, third.commits] == [2, 2, 2]

    runtime._poll_redis_sources()

    assert first.read_blocks == [None, 0, 0]
    assert second.read_blocks == [0, None, 0]
    assert third.read_blocks == [0, 0, None]
