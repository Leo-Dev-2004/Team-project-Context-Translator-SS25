import asyncio
import websockets

async def test_websocket():
    try:
        async with websockets.connect('ws://localhost:8000/ws') as websocket:
            test_msg = {"test": "data"}
            await websocket.send(str(test_msg))
            response = await websocket.recv()
            print("Received:", response)
    except Exception as e:
        print(f"WebSocket error: {e}")

if __name__ == "__main__":
    asyncio.run(test_websocket())
