import pytest
from Backend.QueueManager.shared_queue import (
    to_frontend_queue,
    from_frontend_queue,
    MessageQueue
)

def test_message_queue_basic():
    q = MessageQueue()
    test_msg = {"test": "data"}
    q.enqueue(test_msg)
    assert q.dequeue() == test_msg
    assert q.size() == 0

@pytest.mark.asyncio
async def test_websocket_flow():
    # This would need async test client setup
    pass
