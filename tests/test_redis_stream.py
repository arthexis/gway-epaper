from pathlib import Path

from gway_epaper.sources.redis_stream import RedisStreamSource


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


class FakeRedis:
    def __init__(self, *, latest=None, responses=None, failures=None):
        self.latest = latest or []
        self.responses = list(responses or [])
        self.failures = list(failures or [])
        self.xread_calls = []
        self.xrevrange_calls = []

    def xrevrange(self, stream, count=1):
        self.xrevrange_calls.append((stream, count))
        return self.latest

    def xread(self, streams, *, count, block):
        self.xread_calls.append((streams, count, block))
        if self.failures:
            failure = self.failures.pop(0)
            if failure is not None:
                raise failure
        if self.responses:
            return self.responses.pop(0)
        return []


def auth(entry_id: str, *, id_tag: str = "04A1B2C3", status: str = "Accepted"):
    return (
        entry_id,
        {
            "type": "ocpp.authorization",
            "charger_id": "gway-001",
            "id_tag": id_tag,
            "status": status,
            "reason": "allowed",
            "original": '{"idTag":"04A1B2C3"}',
            "raw": '[2,"msg-1","Authorize",{"idTag":"04A1B2C3"}]',
        },
    )


def test_reads_auth_events_in_order_without_deduplicating(tmp_path: Path) -> None:
    cursor = tmp_path / "auth.cursor"
    client = FakeRedis(
        responses=[
            [
                (
                    "arthexis:events",
                    [auth("1000-0"), auth("1001-0"), auth("1002-0")],
                )
            ]
        ]
    )
    source = RedisStreamSource(
        "auth",
        url="redis://localhost:6379/0",
        stream="arthexis:events",
        start="0-0",
        cursor_file=cursor,
        event_types=("ocpp.authorization",),
        client=client,
    )

    items = source.read_available()

    assert [item.source_id for item in items] == ["1000-0", "1001-0", "1002-0"]
    assert [item.text for item in items] == [
        "AUTH gway-001 04A1B2C3 Accepted (allowed)",
        "AUTH gway-001 04A1B2C3 Accepted (allowed)",
        "AUTH gway-001 04A1B2C3 Accepted (allowed)",
    ]
    assert not cursor.exists()

    source.commit_batch()

    assert cursor.read_text(encoding="utf-8").strip() == "1002-0"
    assert items[0].metadata["original"] == {"idTag": "04A1B2C3"}
    assert items[0].metadata["raw"][2] == "Authorize"


def test_filtering_still_advances_cursor_after_batch_commit(tmp_path: Path) -> None:
    cursor = tmp_path / "events.cursor"
    client = FakeRedis(
        responses=[
            [
                (
                    "arthexis:events",
                    [("2000-0", {"type": "ocpp.status"}), auth("2001-0")],
                )
            ]
        ]
    )
    source = RedisStreamSource(
        "auth",
        url="redis://localhost:6379/0",
        stream="arthexis:events",
        start="0-0",
        cursor_file=cursor,
        event_types=("ocpp.authorization",),
        client=client,
    )

    items = source.read_available()
    source.commit_batch()

    assert [item.source_id for item in items] == ["2001-0"]
    assert cursor.read_text(encoding="utf-8").strip() == "2001-0"


def test_durable_cursor_is_used_after_restart(tmp_path: Path) -> None:
    cursor = tmp_path / "auth.cursor"
    cursor.write_text("3000-0\n", encoding="utf-8")
    client = FakeRedis(responses=[])
    source = RedisStreamSource(
        "auth",
        url="redis://localhost:6379/0",
        stream="arthexis:events",
        start="$",
        cursor_file=cursor,
        client=client,
    )

    source.read_available()

    assert client.xrevrange_calls == []
    assert client.xread_calls[0][0] == {"arthexis:events": "3000-0"}


def test_dollar_start_is_resolved_once_to_concrete_baseline(tmp_path: Path) -> None:
    cursor = tmp_path / "auth.cursor"
    client = FakeRedis(latest=[("4000-0", {"type": "ocpp.authorization"})])
    source = RedisStreamSource(
        "auth",
        url="redis://localhost:6379/0",
        stream="arthexis:events",
        start="$",
        cursor_file=cursor,
        client=client,
    )

    source.read_available()
    source.read_available()

    assert client.xrevrange_calls == [("arthexis:events", 1)]
    assert client.xread_calls[0][0] == {"arthexis:events": "4000-0"}
    assert client.xread_calls[1][0] == {"arthexis:events": "4000-0"}
    assert cursor.read_text(encoding="utf-8").strip() == "4000-0"


def test_batch_size_and_block_are_forwarded() -> None:
    client = FakeRedis()
    source = RedisStreamSource(
        "auth",
        url="redis://localhost:6379/0",
        stream="arthexis:events",
        start="0-0",
        batch_size=17,
        block_ms=250,
        client=client,
    )

    source.read_available()

    assert client.xread_calls == [({"arthexis:events": "0-0"}, 17, 250)]


def test_per_read_block_override_can_force_nonblocking_poll() -> None:
    client = FakeRedis()
    source = RedisStreamSource(
        "auth",
        url="redis://localhost:6379/0",
        stream="arthexis:events",
        start="0-0",
        block_ms=750,
        client=client,
    )

    source.read_available(block_ms=0)

    assert client.xread_calls == [({"arthexis:events": "0-0"}, 100, 0)]


def test_reconnect_backoff_skips_reads_until_retry_window() -> None:
    clock = FakeClock()
    client = FakeRedis(failures=[ConnectionError("offline"), None])
    source = RedisStreamSource(
        "auth",
        url="redis://localhost:6379/0",
        stream="arthexis:events",
        start="0-0",
        client=client,
        clock=clock,
    )

    assert source.read_available() == []
    assert len(client.xread_calls) == 1

    clock.now = 0.5
    assert source.read_available() == []
    assert len(client.xread_calls) == 1

    clock.now = 1.0
    assert source.read_available() == []
    assert len(client.xread_calls) == 2


def test_trimmed_cursor_continues_from_first_available_newer_entry(tmp_path: Path) -> None:
    cursor = tmp_path / "events.cursor"
    cursor.write_text("1000-0\n", encoding="utf-8")
    client = FakeRedis(
        responses=[[ ("arthexis:events", [auth("9000-0"), auth("9001-0")]) ]]
    )
    source = RedisStreamSource(
        "auth",
        url="redis://localhost:6379/0",
        stream="arthexis:events",
        start="$",
        cursor_file=cursor,
        client=client,
    )

    items = source.read_available()
    source.commit_batch()

    assert [item.source_id for item in items] == ["9000-0", "9001-0"]
    assert client.xread_calls[0][0] == {"arthexis:events": "1000-0"}
    assert cursor.read_text(encoding="utf-8").strip() == "9001-0"
