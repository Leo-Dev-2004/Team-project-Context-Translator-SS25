import asyncio
import websockets
import json

async def test_websocket():
    async with websockets.connect('ws://localhost:8000/ws') as websocket:
        # Send test message
        test_msg = {"test": "data"}
        await websocket.send(json.dumps(test_msg))
        
        # Get response
        response = await websocket.recv()
        print("Received:", response)

if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(test_websocket())
