from __future__ import annotations

from queue import Empty

from gway_epaper.sources.celery_queue import CeleryQueueSource


class Message:
    def __init__(self, payload):
        self.payload = payload
        self.acked = False

    def ack(self):
        self.acked = True


class Queue:
    def __init__(self, messages):
        self.messages = list(messages)

    def get(self, *, block=False, timeout=None):
        if not self.messages:
            raise Empty
        return self.messages.pop(0)


def test_authorization_event_is_formatted_and_acked_on_commit():
    message = Message(
        {
            "type": "ocpp.authorization",
            "event_id": "evt-1",
            "charger_id": "CP01",
            "id_tag": "ABC123",
            "status": "Accepted",
        }
    )
    source = CeleryQueueSource(
        "auth",
        url="redis://localhost:6379/0",
        queue="ocpp.authorization",
        event_types=("ocpp.authorization",),
        queue_client=Queue([message]),
        block_seconds=0,
    )

    items = source.read_available()

    assert [item.text for item in items] == ["AUTH CP01 ABC123 Accepted"]
    assert items[0].source_id == "evt-1"
    assert message.acked is False

    source.commit_batch()
    assert message.acked is True


def test_filtered_events_are_acked_without_displaying():
    message = Message({"type": "ocpp.status", "charger_id": "CP01"})
    source = CeleryQueueSource(
        "auth",
        url="redis://localhost:6379/0",
        queue="ocpp.authorization",
        event_types=("ocpp.authorization",),
        queue_client=Queue([message]),
        block_seconds=0,
    )

    assert source.read_available() == []
    assert message.acked is True


def test_non_mapping_payload_is_dropped_and_acked():
    message = Message("not-an-event")
    source = CeleryQueueSource(
        "auth",
        url="redis://localhost:6379/0",
        queue="ocpp.authorization",
        queue_client=Queue([message]),
        block_seconds=0,
    )

    assert source.read_available() == []
    assert message.acked is True
