import pytest
import time
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
            # Test connection ack
            ack = await websocket.receive_json()
            assert ack["type"] == "connection_ack"
            
            # Test message roundtrip
            test_msg = {
                "type": "test_message",
                "data": "ping",
                "timestamp": time.time()
            }
            await websocket.send_json(test_msg)
            response = await websocket.receive_json()
            assert response["response"] == "ack"
            assert response["original"]["type"] == "test_message"
            
            # Test ping/pong
            ping_time = time.time()
            await websocket.send_json({
                "type": "ping",
                "timestamp": ping_time
            })
            pong = await websocket.receive_json()
            assert pong["type"] == "pong"
            assert pong["timestamp"] == ping_time
