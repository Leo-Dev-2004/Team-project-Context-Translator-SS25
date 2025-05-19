import asyncio
import websockets
import json
import time
import subprocess
import sys
from datetime import datetime

async def test_websocket():
    """Enhanced WebSocket test with more validations"""
    print(f"\n=== Starting WebSocket test at {datetime.now().isoformat()} ===")
    test_results = {
        'connection': False,
        'message_roundtrip': False,
        'ping_pong': False,
        'error_handling': False,
        'performance': None
    }
    
    try:
        # Test connection
        start_time = time.time()
        # Try multiple connection attempts with increasing timeouts
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                timeout = 5 * (attempt + 1)  # 5s, 10s, 15s
                async with websockets.connect(
                    'ws://localhost:8000/ws',
                    ping_interval=None,
                    open_timeout=timeout,
                    close_timeout=timeout
                ) as websocket:
            connect_time = time.time() - start_time
            test_results['performance'] = {'connect_time': connect_time}
            print(f"Connection established in {connect_time:.3f}s")
            test_results['connection'] = True
            
            # Test message roundtrip
            test_msg = {
                "type": "test_message",
                "data": "ping",
                "timestamp": time.time()
            }
            await websocket.send(json.dumps(test_msg))
            
            # Validate response
            response = json.loads(await websocket.recv())
            assert response.get('response') == 'ack', "Missing ack response"
            assert response.get('original', {}).get('type') == 'test_message', "Invalid message type"
            test_results['message_roundtrip'] = True
            
            # Test ping/pong
            ping_time = time.time()
            await websocket.send(json.dumps({
                "type": "ping",
                "timestamp": ping_time
            }))
            pong = json.loads(await websocket.recv())
            assert pong['type'] == 'pong', "Invalid pong response"
            assert abs(pong['timestamp'] - ping_time) < 0.1, "Pong delay too high"
            test_results['ping_pong'] = True
            
            # Test error handling
            try:
                await websocket.send("invalid json")
                response = await websocket.recv()
                json.loads(response)  # Should fail
                print("Warning: Server accepted invalid JSON")
            except (json.JSONDecodeError, websockets.exceptions.ConnectionClosed):
                test_results['error_handling'] = True
            
            # Performance test
            perf_start = time.time()
            for i in range(10):
                await websocket.send(json.dumps({
                    "type": "perf_test",
                    "count": i,
                    "timestamp": time.time()
                }))
                await websocket.recv()
            perf_time = time.time() - perf_start
            test_results['performance']['message_rate'] = 10/perf_time
            print(f"Performance: {10/perf_time:.1f} msg/sec")
            
        return test_results
        
    except Exception as e:
        print(f"Test failed: {str(e)}")
        return test_results
    finally:
        print("=== Test completed ===")
        print("Results:", json.dumps(test_results, indent=2))

async def run_tests_with_server():
    """Run tests with managed server instance"""
    server = None
    try:
        # Start backend server
        server = subprocess.Popen(
            ["uvicorn", "Backend.backend:app", "--host", "0.0.0.0", "--port", "8000", "--reload"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
    
        # Log server output in real-time
        def log_output(pipe, prefix):
            for line in pipe:
                print(f"{prefix}: {line.strip()}")
    
        threading.Thread(
            target=log_output,
            args=(server.stdout, "Server stdout"),
            daemon=True
        ).start()
        threading.Thread(
            target=log_output,
            args=(server.stderr, "Server stderr"),
            daemon=True
        ).start()
        
        # Wait for server to start with better verification
        max_wait = 30  # seconds
        start_time = time.time()
        while time.time() - start_time < max_wait:
            try:
                # Check both HTTP and WebSocket connectivity
                http_response = requests.get('http://localhost:8000/health', timeout=1)
                if http_response.status_code == 200:
                    try:
                        async with websockets.connect(
                            'ws://localhost:8000/ws',
                            timeout=2,
                            ping_interval=None
                        ) as ws:
                            await ws.close()
                            break
                    except:
                        pass
            except:
                pass
            time.sleep(1)
        else:
            raise TimeoutError(f"Server didn't start within {max_wait} seconds")
        
        # Run tests
        return await test_websocket()
    finally:
        if server:
            server.terminate()
            server.wait()

if __name__ == "__main__":
    # First try direct connection
    print("Trying direct connection...")
    results = asyncio.run(test_websocket())
    
    # If failed, start server and retry
    if not all(results.values()):
        print("\nStarting backend server and retrying...")
        results = asyncio.run(run_tests_with_server())
    
    # Exit with status code
    sys.exit(0 if all(results.values()) else 1)
