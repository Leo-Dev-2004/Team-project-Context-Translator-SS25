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
    from Backend.backend import app
    from httpx import AsyncClient
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        async with client.websocket_connect("/ws") as websocket:
            test_msg = {"test": "data"}
            await websocket.send_json(test_msg)
            response = await websocket.receive_json()
            assert "test" in response
