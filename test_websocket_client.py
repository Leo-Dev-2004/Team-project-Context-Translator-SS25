import asyncio
import websockets
import json
import time
import subprocess
import sys

async def test_websocket():
    print("Starting WebSocket test...")
    try:
        print("Attempting to connect to ws://localhost:8000/ws")
        async with websockets.connect(
            'ws://localhost:8000/ws',
            ping_interval=None,
            open_timeout=5
        ) as websocket:
            print("Connection established")
            
            test_msg = {"type": "test", "data": "ping"}
            print(f"Sending: {test_msg}")
            await websocket.send(json.dumps(test_msg))
            
            response = await websocket.recv()
            print(f"Received: {response}")
            return True
            
    except Exception as e:
        print(f"WebSocket error: {str(e)}")
        return False
    finally:
        print("Test completed")

async def run_tests_with_server():
    # Start backend server
    server = subprocess.Popen(
        ["uvicorn", "Backend.backend:app", "--host", "0.0.0.0", "--port", "8000"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # Wait for server to start
    time.sleep(2)
    
    # Run test
    success = await test_websocket()
    
    # Shutdown server
    server.terminate()
    server.wait()
    
    return success

if __name__ == "__main__":
    # First try direct connection
    print("Trying direct connection...")
    result = asyncio.run(test_websocket())
    
    # If failed, start server and retry
    if not result:
        print("\nStarting backend server and retrying...")
        success = asyncio.run(run_tests_with_server())
        sys.exit(0 if success else 1)
    else:
        sys.exit(0)
