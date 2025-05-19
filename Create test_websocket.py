import pytest
from httpx import AsyncClient
from Backend.backend import app

@pytest.mark.asyncio
async def test_websocket():
    async with AsyncClient(app=app, base_url="http://test") as client:
        async with client.websocket_connect("/ws") as websocket:
            test_msg = {"test": "data"}
            await websocket.send_json(test_msg)
            response = await websocket.receive_json()
            assert "test" in response
