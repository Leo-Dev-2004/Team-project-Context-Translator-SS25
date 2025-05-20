import time
import uvicorn
from Backend.backend import app
from Backend.queues.shared_queue import (
    get_to_frontend_queue,
    get_from_frontend_queue,
    get_to_backend_queue,
    get_from_backend_queue
)

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0", 
        port=8000,
        log_level="info",
        access_log=True
    )
                            
                            # Enhanced queue health checks
                            def check_queue_health():
                                # Check for processing delays
                                if to_backend_queue.size() > 5 and from_backend_queue.size() == 0:
                                    print("\n⚠️ CRITICAL: Messages not being processed from to_backend_queue!")
                                    try:
                                        msg = to_backend_queue._queue[0]  # Peek without dequeue
                                        age = time.time() - msg.get('timestamp', time.time())
                                        print(f"Oldest message age: {age:.2f} seconds")
                                        print(f"Message ID: {msg.get('data', {}).get('id', 'no-id')}")
                                    except Exception as e:
                                        print(f"Error inspecting queue: {str(e)}")
                                
                                # Check for forwarding delays
                                if from_backend_queue.size() > 5 and to_frontend_queue.size() < 2:
                                    print("\n⚠️ WARNING: Messages not being forwarded to frontend!")
                                    try:
                                        msg = from_backend_queue._queue[0]
                                        age = time.time() - msg.get('timestamp', time.time())
                                        print(f"Oldest message age: {age:.2f} seconds")
                                        print(f"Message ID: {msg.get('data', {}).get('id', 'no-id')}")
                                    except Exception as e:
                                        print(f"Error inspecting queue: {str(e)}")
                                
                                # Check for websocket delivery
                                if to_frontend_queue.size() > 10 and len(app.state.websockets) > 0:
                                    print("\n⚠️ WARNING: Messages accumulating in to_frontend_queue despite active WebSocket!")
                            
                            check_queue_health()
                            
                            # Detailed queue inspection
                            def inspect_queue(queue, name):
                                if queue.size() == 0:
                                    print(f"\n{name}: EMPTY")
                                    return
                                
                                print(f"\n{name}: {queue.size()} items")
                                print(f"First item:")
                                try:
                                    item = queue._queue[0]
                                    print(f"  ID: {item.get('data', {}).get('id', 'no-id')}")
                                    print(f"  Type: {item.get('type', 'unknown')}")
                                    print(f"  Status: {item.get('data', {}).get('status', 'unknown')}")
                                    print(f"  Timestamp: {item.get('timestamp')}")
                                    print(f"  Path: {item.get('processing_path', [])}")
                                except Exception as e:
                                    print(f"  Error inspecting: {str(e)}")
                            
                            inspect_queue(to_frontend_queue, "to_frontend_queue")
                            inspect_queue(from_frontend_queue, "from_frontend_queue") 
                            inspect_queue(to_backend_queue, "to_backend_queue")
                            inspect_queue(from_backend_queue, "from_backend_queue")
                            
                            time.sleep(2)
                        break
                    else:
                        print(f"Failed to start simulation: {response.json()}")
                else:
                    print(f"Backend not ready yet (HTTP {health.status_code})")
            except Exception as e:
                print(f"Error connecting to backend: {str(e)}")
            
            retry_count += 1
            time.sleep(1)
        
        if retry_count >= max_retries:
            print("Failed to start simulation after maximum retries")

def run_frontend_server(self):
        """Run the frontend HTTP server"""
        logger.info("Starting frontend HTTP server...")
        frontend = subprocess.Popen(
            ["python", "-m", "http.server", "9000", "--directory", "Frontend"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        self.processes.append(frontend)
        
        # Log frontend server output in real-time
        def log_output(pipe, prefix):
            for line in pipe:
                logger.debug(f"{prefix}: {line.strip()}")
                
        threading.Thread(
            target=log_output,
            args=(frontend.stdout, "Frontend stdout"),
            daemon=True
        ).start()
        threading.Thread(
            target=log_output,
            args=(frontend.stderr, "Frontend stderr"),
            daemon=True
        ).start()
        
        logger.info("Frontend server started on port 9000")

        def open_browser(self):
            """Open the frontend in browser"""
            logger.info("Waiting 3 seconds before opening browser...")
            time.sleep(3)
            url = "http://localhost:9000/index.html"
            logger.info(f"Opening browser to {url}")
            webbrowser.open(url)

        def shutdown(self, signum, frame):
            """Clean shutdown handler"""
            print("\nShutting down system...")
            self.running = False
            for p in self.processes:
                p.terminate()
            sys.exit(0)

async def run_async_tasks(self):
        """Run async tasks in event loop"""
        from Backend.queues.shared_queue import (
            to_frontend_queue,
            from_frontend_queue,
            to_backend_queue,
            from_backend_queue
        )
        
        # Verify queues are initialized
        if None in [to_frontend_queue, from_frontend_queue, to_backend_queue, from_backend_queue]:
            logger.error("Queues not properly initialized!")
            return
            
        logger.info("Starting async tasks with initialized queues...")
        await asyncio.gather(
            process_messages(),
            forward_messages()
        )

if __name__ == "__main__":
    logger.info("Starting system...")
    uvicorn.run(
        app,
        host="0.0.0.0", 
        port=8000,
        log_level="info",
        access_log=True
    )
