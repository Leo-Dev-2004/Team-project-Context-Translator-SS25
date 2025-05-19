import asyncio
from httpx import AsyncClient
from Backend.backend import app

async def test_websocket():
    async with AsyncClient(app=app, base_url="http://test") as client:
        async with client.websocket_connect("/ws") as websocket:
            test_msg = {"test": "data"}
            await websocket.send_json(test_msg)
            response = await websocket.receive_json()
            print("Received:", response)

if __name__ == "__main__":
    asyncio.run(test_websocket())
