from fastapi import FastAPI, WebSocket, BackgroundTasks
import asyncio
import random
from fastapi.middleware.cors import CORSMiddleware
from Backend.QueueManager.shared_queue import (
    MessageQueue,
    to_frontend_queue,
    from_frontend_queue,
    to_backend_queue,
    from_backend_queue
)

# Configure queue sizes
MAX_QUEUE_SIZE = 100  # Prevent memory overflows
to_frontend_queue = MessageQueue()
from_frontend_queue = MessageQueue()
to_backend_queue = MessageQueue()
from_backend_queue = MessageQueue()
import asyncio
import json
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('backend.log')
    ]
)
import time

app = FastAPI()
app.state.websockets = set()  # Track active WebSocket connections

@app.get("/")
async def root():
    return {"message": "Welcome to the Context Translator API"}

# Simulation state
simulation_running = False
simulation_task = None

async def simulate_entries():
    """Background task to simulate queue entries"""
    global simulation_running
    simulation_running = True
    
    print("\n=== SIMULATION STARTING ===")
    print("Initializing queues...")
    
    # Initial system message with proper structure
    system_msg = {
        "type": "system",
        "data": {
            "id": "sys_init",
            "message": "Simulation started",
            "status": "pending"
        },
        "timestamp": time.time()
    }
    print(f"\nEnqueuing initial system message: {system_msg}")
    to_backend_queue.enqueue(system_msg)
    print(f"to_backend_queue size: {to_backend_queue.size()}")
    
    counter = 0
    while simulation_running:
        counter += 1
        await asyncio.sleep(1)  # Generate messages every second
        
        # Monitor queue health
        if to_backend_queue.size() > 5:
            print(f"⚠️ WARNING: to_backend_queue has {to_backend_queue.size()} messages")
            try:
                oldest_msg = to_backend_queue._queue[0]
                age = time.time() - oldest_msg.get('timestamp', time.time())
                print(f"Oldest message age: {age:.2f}s (ID: {oldest_msg.get('data', {}).get('id')})")
            except Exception as e:
                print(f"Error checking queue: {str(e)}")
        
        # Create simulation message and block until enqueued
        sim_msg = {
            "type": "simulation",
            "data": {
                "id": f"sim_{counter}",
                "content": f"Simulation message {counter}",
                "status": "pending",
                "progress": 0,
                "created_at": time.time()
            },
            "timestamp": time.time()
        }
        
        # This will block if queue is full
        to_backend_queue.enqueue(sim_msg)
        print(f"Enqueued message {counter} to to_backend_queue")
        
        print(f"\nGenerated simulation message {counter}: {sim_msg['data']['id']}")
        to_backend_queue.enqueue(sim_msg)
        print(f"Current to_backend_queue size: {to_backend_queue.size()}")
        
        # Create entry data structure
        entry = {
            "id": f"entry_{counter}",
            "type": "simulation",
            "content": f"Simulation entry {counter}",
            "status": "pending",
            "timestamp": time.time()
        }
        
        print(f"Generating entry {counter}: {entry}")
        
        # Randomize queue destinations
        if counter % 4 == 0:
            # Send directly to backend
            backend_msg = {
                "type": "backend_message",
                "data": entry,
                "status": "processing",
                "timestamp": time.time()
            }
            to_backend_queue.enqueue(backend_msg)
        else:
            # Normal frontend flow
            frontend_msg = {
                "type": "frontend_message",
                "data": entry,
                "status": "created",
                "timestamp": time.time()
            }
            to_frontend_queue.enqueue(frontend_msg)
        
        # Random delay between 0.5-2 seconds
        await asyncio.sleep(0.5 + 1.5 * random.random())
    
    print("Simulation stopped")

@app.on_event("shutdown")
def shutdown_event():
    global simulation_running
    simulation_running = False

@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "0.1"}

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:9000", "http://127.0.0.1:9000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    client = websocket.client
    if client:
        logging.info(f"WebSocket connection request from {client.host}:{client.port}")
    else:
        logging.info("WebSocket connection request from an unknown client")
    
    # Set fast timeout for initial handshake
    # Set a timeout for the WebSocket handshake
    try:
        await asyncio.wait_for(websocket.accept(), timeout=5.0)
    except asyncio.TimeoutError:
        logging.error("WebSocket handshake timed out")
        return
    
    try:
        await websocket.accept()
        if not hasattr(app.state, 'websockets'):
            app.state.websockets = set()
        app.state.websockets.add(websocket)
        
        # Send immediate connection confirmation
        await websocket.send_text(json.dumps({
            'type': 'connection_ack',
            'status': 'connected',
            'timestamp': time.time()
        }))
        
        if client:
            logging.info(f"WebSocket connection established with {client.host}:{client.port}")
        else:
            logging.info("WebSocket connection established with an unknown client")
        logging.info(f"Current WebSocket connections: {len(app.state.websockets)}")
    except Exception as e:
        logging.error(f"WebSocket accept failed: {e}")
        raise
    
    # Start all processing tasks
    processor_task = asyncio.create_task(process_messages())
    forwarder_task = asyncio.create_task(forward_messages())
    sender_task = asyncio.create_task(send_messages(websocket))
    receiver_task = asyncio.create_task(receive_messages(websocket))
    
    try:
        await asyncio.gather(sender_task, receiver_task)
    except asyncio.CancelledError:
        logging.info("WebSocket tasks cancelled normally")
    except Exception as e:
        logging.error(f"WebSocket error: {e}")
    finally:
        if not sender_task.done():
            sender_task.cancel()
        if not receiver_task.done():
            receiver_task.cancel()
        try:
            await asyncio.wait_for(websocket.close(), timeout=1.0)
        except Exception:
            pass
        logging.info("WebSocket connection closed")

async def process_messages():
    """Process messages through the full pipeline with blocking behavior"""
    print("\nStarting blocking message processor pipeline...")
    while True:
        try:
            # Block until we get a message from to_backend_queue
            print(f"\n[Processor] Waiting for message in to_backend_queue...")
            backend_msg = to_backend_queue.dequeue()  # Blocks until available
                
            if backend_msg is not None:
                print(f"\n[Processor] Processing message ID: {backend_msg.get('data', {}).get('id', 'no-id')}")
            else:
                print("\n[Processor] Received None as backend_msg")
            print(f"Message content: {json.dumps(backend_msg, indent=2)}")
            
            # Add processing metadata
            if backend_msg is not None:
                backend_msg.setdefault('processing_path', [])
            else:
                logging.error("backend_msg is None, skipping processing.")
                continue
            backend_msg['processing_path'].append({
                'stage': 'processing_start',
                'queue_size': from_backend_queue.size(),
                'timestamp': time.time()
            })
            
            # Forward to from_backend_queue with verification
            prev_size = from_backend_queue.size()
            from_backend_queue.enqueue(backend_msg)
            new_size = from_backend_queue.size()
            
            if new_size <= prev_size:
                print(f"⚠️ CRITICAL: Failed to enqueue in from_backend_queue! (before: {prev_size}, after: {new_size})")
                # Emergency dump the message
                print(f"Failed message: {json.dumps(backend_msg, indent=2)}")
                # Try one more time
                from_backend_queue.enqueue(backend_msg)
            else:
                print(f"✅ Successfully enqueued in from_backend_queue (new size: {new_size})")
            
            # Simulate processing
            await asyncio.sleep(1)
            
            # Update status and path tracking
            backend_msg['status'] = 'processed'
            backend_msg['timestamp'] = time.time()
            backend_msg['processing_path'].append({
                'stage': 'processing_complete', 
                'queue_size': to_frontend_queue.size(),
                'timestamp': time.time()
            })
            
            # Forward to next queue with verification
            prev_size = to_frontend_queue.size()
            to_frontend_queue.enqueue(backend_msg)
            new_size = to_frontend_queue.size()
            
            if new_size <= prev_size:
                print(f"⚠️ CRITICAL: Failed to enqueue in to_frontend_queue! (before: {prev_size}, after: {new_size})")
            else:
                print(f"✅ Successfully forwarded to to_frontend_queue (new size: {new_size})")
                print(f"Forwarded to to_frontend_queue (size: {to_frontend_queue.size()})")
                
                # Ensure all messages get routed to frontend
                if backend_msg.get('type') in ('simulation', 'test_message', 'system'):
                    # Convert to frontend format
                    frontend_msg = {
                        'type': 'frontend_update',
                        'data': backend_msg,
                        'timestamp': time.time()
                    }
                    print(f"\n[Processor] Routing to frontend: {frontend_msg}")
                    to_frontend_queue.enqueue(frontend_msg)
                    print(f"to_frontend_queue size: {to_frontend_queue.size()}")
                    logging.info(f"Routed to frontend: {frontend_msg}")
                    # Simulate processing with progress updates
                    for progress in range(0, 101, 20):
                        await asyncio.sleep(0.5)
                        update_msg = {
                            **backend_msg,
                            "data": {
                                **backend_msg.get('data', {}),
                                "status": "processing",
                                "progress": progress
                            },
                            "timestamp": time.time()
                        }
                        from_backend_queue.enqueue(update_msg)
                    
                    # Final processed message
                    backend_msg['status'] = 'processed'
                    backend_msg['timestamp'] = time.time()
                    backend_msg['data']['progress'] = 100
                    from_backend_queue.enqueue(backend_msg)
                    logging.info(f"Simulation message processed: {backend_msg}")
                else:
                    # Default processing for other messages
                    await asyncio.sleep(1)
                    backend_msg['status'] = 'processed'
                    backend_msg['timestamp'] = time.time()
                    from_backend_queue.enqueue(backend_msg)
                    logging.info(f"Message processed: {backend_msg}")
                
        except Exception as e:
            logging.error(f"Error processing message: {e}")
            await asyncio.sleep(1)

async def forward_messages():
    """Forward messages between queues with blocking behavior"""
    print("\nStarting blocking queue forwarder...")
    while True:
        try:
            # Block until we get a message from from_backend_queue
            print("\n[Forwarder] Waiting for message in from_backend_queue...")
            msg = from_backend_queue.dequeue()  # Blocks until available
            
            if msg is None:
                print("⚠️ WARNING: Received None message in forward_messages")
                continue
                
            print(f"\n[Forwarder] Moving message ID: {msg.get('data', {}).get('id', 'no-id')}")
            print(f"Message path: {msg.get('processing_path', [])}")
            print(f"Queue sizes - from_backend: {from_backend_queue.size()}, to_frontend: {to_frontend_queue.size()}")
            
            # Track forwarding path
            if msg is not None:
                msg.setdefault('forwarding_path', [])
            if msg is not None:
                msg.setdefault('forwarding_path', [])
                msg['forwarding_path'].append({
                    'from': 'from_backend_queue',
                    'to': 'to_frontend_queue',
                    'timestamp': time.time()
                })
            else:
                logging.warning("Attempted to process a None message in forward_messages")
            
            # Verify enqueue operation
            prev_size = to_frontend_queue.size()
            if msg is not None:
                if msg is not None:
                    if msg is not None:
                        if msg is not None:
                            if msg is not None:
                                to_frontend_queue.enqueue(msg)
                            else:
                                logging.warning("Attempted to enqueue a None message to to_frontend_queue")
                        else:
                            logging.warning("Attempted to enqueue a None message to to_frontend_queue")
                    else:
                        logging.warning("Attempted to enqueue a None message to to_frontend_queue")
                else:
                    logging.warning("Attempted to enqueue a None message to to_frontend_queue")
            new_size = to_frontend_queue.size()
            
            if new_size <= prev_size:
                print(f"⚠️ WARNING: to_frontend_queue size didn't increase! (before: {prev_size}, after: {new_size})")
                # Emergency handling - try once more
                to_frontend_queue.enqueue(msg)
                if to_frontend_queue.size() <= new_size:
                    print("⚠️ CRITICAL: Retry failed! Message lost!")
                    # At least log the message
                    print(f"Lost message: {json.dumps(msg, indent=2)}")
            else:
                print(f"✅ Forwarded successfully (new to_frontend size: {new_size})")

            # Forward from_frontend_queue -> to_backend_queue (new messages)
            if from_frontend_queue.size() > 0:
                frontend_msg = from_frontend_queue.dequeue()
                if frontend_msg:
                    # Mark as new for backend processing
                    frontend_msg['status'] = 'new_for_backend' 
                    to_backend_queue.enqueue(frontend_msg)
                    print(f"→ Forwarded to to_backend_queue (size: {to_backend_queue.size()})")

            await asyncio.sleep(0.1)
        except Exception as e:
            print(f"Error in queue forwarding: {e}")
            await asyncio.sleep(1)

async def send_messages(websocket: WebSocket):
    """Send messages from to_frontend_queue to client with blocking"""
    client = websocket.client
    try:
        while True:
            try:
                # Block until we get a message to send
                print("\n[Sender] Waiting for message in to_frontend_queue...")
                message = to_frontend_queue.dequeue()  # Blocks until available
                
                try:
                    # Mark as sent to frontend
                    if message is not None:
                        message['status'] = 'sent_to_frontend'
                    else:
                        logging.warning("Attempted to process a None message in send_messages")
                    if message is not None:
                        message['timestamp'] = time.time()
                    else:
                        logging.warning("Attempted to process a None message in receive_messages")
                    msg_str = json.dumps(message)
                    client_info = f"{client.host}:{client.port}" if client else "unknown client"
                    logging.debug(f"Sending to {client_info}: {msg_str[:200]}...")
                    await websocket.send_text(msg_str)
                    
                    # Queue for next cycle if needed
                    if message.get('cycles_completed', 0) < 1:
                        message['cycles_completed'] = message.get('cycles_completed', 0) + 1
                        from_frontend_queue.enqueue(message)
                        print(f"→ Queued for next cycle in from_frontend_queue (size: {from_frontend_queue.size()})")
                except RuntimeError as e:
                        if "disconnect" in str(e):
                            logging.info("WebSocket disconnected during send")
                            break
                        raise
                except Exception as e:
                        logging.error(f"Failed to send message: {e}")
                        if message is not None:
                            from_frontend_queue.enqueue(message)  # Requeue if failed
                        else:
                            logging.warning("Attempted to enqueue a None message to from_frontend_queue")
                await asyncio.sleep(0.1)  # Prevent busy waiting
            except Exception as e:
                logging.error(f"Error in send loop: {e}")
                break
    except Exception as e:
        logging.error(f"WebSocket send task failed: {e}")
    finally:
        logging.info("WebSocket send task ending")

@app.get("/simulation/start")
async def start_simulation(background_tasks: BackgroundTasks):
    # Clear any existing messages first
    to_backend_queue._queue.clear()
    from_backend_queue._queue.clear()
    to_frontend_queue._queue.clear()
    from_frontend_queue._queue.clear()
    """Start the queue simulation"""
    global simulation_task, simulation_running
    if not simulation_running:
        simulation_running = True
        simulation_task = background_tasks.add_task(simulate_entries)
        
        # Send initial system message
        system_msg = {
            "type": "system",
            "data": {
                "id": "sys_start",
                "message": "Simulation started via HTTP",
                "status": "info"
            },
            "timestamp": time.time()
        }
        to_frontend_queue.enqueue(system_msg)
        
        return {
            "status": "simulation started",
            "message": "Simulation messages will begin flowing through queues"
        }
    return {"status": "simulation already running"}

@app.get("/simulation/stop")
async def stop_simulation():
    """Stop the queue simulation"""
    global simulation_running
    simulation_running = False
    return {"status": "simulation stopping"}

@app.get("/simulation/status")
async def simulation_status():
    """Get detailed simulation status"""
    def get_queue_stats(queue):
        if queue.size() == 0:
            return {
                "size": 0,
                "oldest": None,
                "newest": None
            }
        return {
            "size": queue.size(),
            "oldest": queue._queue[0]['timestamp'] if queue.size() > 0 else None,
            "newest": queue._queue[-1]['timestamp'] if queue.size() > 0 else None
        }
    
    def calculate_rate(queue):
        if queue.size() < 2:
            return 0
        time_span = queue._queue[-1]['timestamp'] - queue._queue[0]['timestamp']
        return queue.size() / time_span if time_span > 0 else 0
    
    return {
        "running": simulation_running,
        "queues": {
            "to_frontend": get_queue_stats(to_frontend_queue),
            "from_frontend": get_queue_stats(from_frontend_queue),
            "to_backend": get_queue_stats(to_backend_queue),
            "from_backend": get_queue_stats(from_backend_queue)
        },
        "message_rates": {
            "to_frontend": calculate_rate(to_frontend_queue),
            "from_frontend": calculate_rate(from_frontend_queue),
            "to_backend": calculate_rate(to_backend_queue),
            "from_backend": calculate_rate(from_backend_queue)
        },
        "websockets": len(app.state.websockets) if hasattr(app.state, 'websockets') else 0,
        "timestamp": time.time()
    }

@app.get("/queues/debug")
async def debug_queues():
    """Debug endpoint to show detailed queue contents"""
    def get_queue_details(queue):
        try:
            items = []
            # Get queue items
            if hasattr(queue, '_queue'):  # MessageQueue
                queue_items = list(queue._queue)
            elif hasattr(queue, 'copy'):  # deque
                queue_items = list(queue.copy())
            else:
                return [{"error": "Unknown queue type"}]
            
            # Extract key details from each item
            for item in queue_items[:20]:  # Limit to first 20 items
                details = {
                    "type": item.get('type', 'unknown'),
                    "timestamp": item.get('timestamp'),
                    "processing_path": item.get('processing_path', []),
                    "forwarding_path": item.get('forwarding_path', []),
                    "size_bytes": len(str(item))
                }
                
                # Add data-specific fields
                if 'data' in item:
                    data = item['data']
                    details.update({
                        "id": data.get('id'),
                        "status": data.get('status'),
                        "progress": data.get('progress'),
                        "message": data.get('message') or data.get('content')
                    })
                
                items.append(details)
            return items
        except Exception as e:
            return [{"error": str(e)}]
    
    return {
        "to_frontend_queue": {
            "size": to_frontend_queue.size(),
            "items": get_queue_details(to_frontend_queue)
        },
        "from_frontend_queue": {
            "size": from_frontend_queue.size(),
            "items": get_queue_details(from_frontend_queue)
        },
        "to_backend_queue": {
            "size": to_backend_queue.size(),
            "items": get_queue_details(to_backend_queue)
        },
        "from_backend_queue": {
            "size": from_backend_queue.size(),
            "items": get_queue_details(from_backend_queue)
        }
    }

async def receive_messages(websocket: WebSocket):
    """Receive messages from client and add to from_frontend_queue"""
    client = websocket.client
    try:
        while True:
            try:
                data = await websocket.receive_text()
                message = json.loads(data)
                
                # Handle ping messages immediately
                if message.get('type') == 'ping':
                    await websocket.send_text(json.dumps({
                        'type': 'pong',
                        'timestamp': message['timestamp'],
                        'server_time': time.time()
                    }))
                    continue
                    
                # Send connection ack on first message
                if not getattr(websocket, '_connection_ack_sent', False):
                    await websocket.send_text(json.dumps({
                        'type': 'connection_ack',
                        'status': 'connected',
                        'timestamp': time.time()
                    }))
                    websocket._connection_ack_sent = True
                logging.debug(f"Received from {client.host}:{client.port}: {data[:200]}...")
                message = json.loads(data)
                # Mark as received from frontend
                if not message.get('status'):
                    message['status'] = 'received_from_frontend'
                message['timestamp'] = time.time()
                from_frontend_queue.enqueue(message)
                print(f"← Received from frontend, queued in from_frontend_queue (size: {from_frontend_queue.size()})")
                
                # Send response
                response = {"response": "ack", "original": message}
                await websocket.send_text(json.dumps(response))
                print("Sent response")  # Debug
                
            except json.JSONDecodeError as e:
                logging.error(f"Invalid JSON received: {e}")
            except RuntimeError as e:
                if "disconnect" in str(e):
                    logging.info("WebSocket disconnected during receive")
                    break
                raise
            except Exception as e:
                logging.error(f"Failed to process message: {e}")
                break
    except Exception as e:
        logging.error(f"WebSocket receive task failed: {e}")
    finally:
        logging.info("WebSocket receive task ending")
