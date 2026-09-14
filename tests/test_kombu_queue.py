from queue import Empty
from unittest.mock import Mock

from gway_epaper.sources.kombu_queue import KombuQueueSource


def _message(payload):
    message = Mock()
    message.payload = payload
    message.delivery_tag = "delivery-1"
    return message


def test_queue_source_formats_authorization_and_acks_on_commit() -> None:
    connection = Mock()
    queue = Mock()
    connection.SimpleQueue.return_value = queue
    message = _message(
        {
            "type": "ocpp.authorization",
            "charger_id": "charger-1",
            "id_tag": "04A1B2C3",
            "status": "Accepted",
            "reason": "local policy",
            "message_id": "msg-7",
        }
    )
    queue.get.side_effect = [message, Empty()]
    source = KombuQueueSource(
        "auth",
        url="redis://localhost:6379/0",
        queue_name="ocpp.authorization",
        event_types=("ocpp.authorization",),
        connection=connection,
        block_seconds=0,
    )

    items = source.read_available()

    assert len(items) == 1
    assert items[0].text == "AUTH charger-1 04A1B2C3 Accepted (local policy)"
    assert items[0].source_id == "msg-7"
    message.ack.assert_not_called()

    source.commit_batch()
    message.ack.assert_called_once_with()


def test_queue_source_acknowledges_filtered_messages_on_commit() -> None:
    connection = Mock()
    queue = Mock()
    connection.SimpleQueue.return_value = queue
    message = _message({"type": "unrelated.event"})
    queue.get.side_effect = [message, Empty()]
    source = KombuQueueSource(
        "auth",
        url="redis://localhost:6379/0",
        queue_name="ocpp.authorization",
        event_types=("ocpp.authorization",),
        connection=connection,
        block_seconds=0,
    )

    assert source.read_available() == []
    source.commit_batch()

    message.ack.assert_called_once_with()


def test_queue_source_leaves_messages_unacked_until_batch_commits() -> None:
    connection = Mock()
    queue = Mock()
    connection.SimpleQueue.return_value = queue
    message = _message({"type": "ocpp.authorization", "status": "Accepted"})
    queue.get.side_effect = [message, Empty()]
    source = KombuQueueSource(
        "auth",
        url="redis://localhost:6379/0",
        queue_name="ocpp.authorization",
        connection=connection,
        block_seconds=0,
    )

    assert source.read_available()
    assert source.read_available() == []
    message.ack.assert_not_called()
