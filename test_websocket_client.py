import asyncio
import websockets
import json
import time

async def test_websocket():
    print("Starting WebSocket test...")
    try:
        print("Attempting to connect to ws://localhost:8000/ws")
        async with websockets.connect(
            'ws://localhost:8000/ws',
            ping_interval=None,
            open_timeout=10
        ) as websocket:
            print("Connection established")
            
            test_msg = {"type": "test", "data": "ping"}
            print(f"Sending: {test_msg}")
            await websocket.send(json.dumps(test_msg))
            
            # Immediately wait for response
            response = await websocket.recv()
            print(f"Received: {response}")
            return
            
            print("Waiting for response...")
            start_time = time.time()
            while time.time() - start_time < 5:  # Wait max 5 seconds
                try:
                    response = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                    print(f"Received: {response}")
                    return
                except asyncio.TimeoutError:
                    print("Waiting...")
            
            print("No response received within 5 seconds")
    except Exception as e:
        print(f"WebSocket error: {str(e)}")
    finally:
        print("Test completed")

if __name__ == "__main__":
    asyncio.run(test_websocket())
