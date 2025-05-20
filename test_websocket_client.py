import asyncio
import aiohttp
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
        'performance': None,
        'server_status': None
    }
    
    try:
        # First check if HTTP server is running
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get('http://localhost:8000/health', timeout=2) as resp:
                    test_results['server_status'] = f"HTTP {resp.status}"
                    if resp.status != 200:
                print(f"HTTP server not healthy: {http_response.status_code}")
                return test_results
        except Exception as e:
            test_results['server_status'] = f"HTTP error: {str(e)}"
            print(f"HTTP check failed: {e}")
            return test_results

        # Test connection
        start_time = time.time()
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                timeout = 5 * (attempt + 1)  # 5s, 10s, 15s
                print(f"Attempt {attempt+1} with timeout {timeout}s...")
                
                try:
                    websocket = await websockets.connect(
                        'ws://localhost:8000/ws', 
                        ping_interval=None
                    )
                    # Verify connection with ping/pong
                    ping_time = time.time()
                    await websocket.send(json.dumps({
                        "type": "ping",
                        "timestamp": ping_time
                    }))
                    pong = await asyncio.wait_for(websocket.recv(), timeout=timeout)
                    pong_data = json.loads(pong)
                    if pong_data.get("type") != "pong":
                        raise ConnectionError("Invalid pong response")
                    connect_time = time.time() - start_time
                    test_results['performance'] = {'connect_time': connect_time}
                    print(f"Connection established in {connect_time:.3f}s")
                    test_results['connection'] = True
                except Exception as e:
                    print(f"Error during WebSocket connection: {e}")
            except Exception as e:
                print(f"Connection attempt {attempt+1} failed: {e}")

                # Test message roundtrip
                test_msg = {
                        "type": "test_message",
                        "data": "ping",
                        "timestamp": datetime.now().timestamp()
                    }
                await websocket.send(json.dumps(test_msg))
                continue
            
            # Validate response
            try:
                response = json.loads(await websocket.recv())
                assert response.get('response') == 'ack', "Missing ack response"
                assert response.get('original', {}).get('type') == 'test_message', "Invalid message type"
                test_results['message_roundtrip'] = True
            except Exception as e:
                print(f"Message validation failed: {e}")
                test_results['message_roundtrip'] = False
            
            # Test ping/pong
            try:
                ping_time = time.time()
                await websocket.send(json.dumps({
                    "type": "ping",
                    "timestamp": ping_time
                }))
                pong = json.loads(await websocket.recv())
                assert pong['type'] == 'pong', "Invalid pong response"
                assert abs(pong['timestamp'] - ping_time) < 0.1, "Pong delay too high"
                test_results['ping_pong'] = True
            except Exception as e:
                print(f"Ping/pong test failed: {e}")
                test_results['ping_pong'] = False
            
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
        # First kill any existing server on port 8000
        try:
            subprocess.run(["fuser", "-k", "8000/tcp"], check=True)
            time.sleep(1)  # Give it time to release the port
        except:
            pass  # Ignore if no process was found
        
        # Start backend server with explicit log level and bind to all interfaces
        server = subprocess.Popen(
            ["uvicorn", "Backend.backend:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "debug"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        # Verify server process started
        if server.poll() is not None:
            raise RuntimeError("Server process failed to start")
    
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
        server_ready = False
        
        while time.time() - start_time < max_wait:
            try:
                # Check HTTP health endpoint first
                async with aiohttp.ClientSession() as session:
                    async with session.get('http://localhost:8000/health', timeout=1) as resp:
                        if resp.status == 200:
                    # Then verify WebSocket connection
                    try:
                        try:
                            ws = await websockets.connect(
                                'ws://localhost:8000/ws',
                                ping_interval=None
                            )
                            await ws.send(json.dumps({"type": "ping"}))
                            response = await asyncio.wait_for(ws.recv(), timeout=2)
                            if json.loads(response).get("type") == "pong":
                                server_ready = True
                                await ws.close()
                                break
                        except Exception as e:
                            print(f"WebSocket check failed: {e}")
                        finally:
                            if 'ws' in locals():
                                await ws.close()
                    except Exception as e:
                        print(f"WebSocket check failed: {e}")
            except Exception as e:
                print(f"HTTP check failed: {e}")
            
            print(f"Waiting for server to start... ({int(time.time() - start_time)}s)")
            time.sleep(1)
            
        if not server_ready:
            raise TimeoutError(f"Server didn't become ready within {max_wait} seconds")
        
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
