import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import asyncio
from .queues.shared_queue import (
    get_initialized_queues,
    get_to_backend_queue,
    get_to_frontend_queue,
    get_from_backend_queue
)
from .core.simulator import SimulationManager
from .core.message_processor import MessageProcessor
from .core.queue_forwarder import QueueForwarder
from .api import endpoints
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
    logging.info("Simulation task starting")
    
    def validate_message(msg: dict) -> bool:
        required_fields = {'type', 'data', 'timestamp'}
        return all(field in msg for field in required_fields)
    
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
    await to_backend_queue.enqueue(system_msg)
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
        await to_backend_queue.enqueue(sim_msg)
        print(f"Enqueued message {counter} to to_backend_queue")
        print(f"\nGenerated simulation message {counter}: {sim_msg['data']['id']}")
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
            await to_backend_queue.enqueue(backend_msg)
        else:
            # Normal frontend flow
            frontend_msg = {
                "type": "frontend_message",
                "data": entry,
                "status": "created",
                "timestamp": time.time()
            }
            await to_frontend_queue.enqueue(frontend_msg)
        
        # Random delay between 0.5-2 seconds
        await asyncio.sleep(0.5 + 1.5 * random.random())
    
    print("Simulation stopped")

@app.on_event("shutdown")
def shutdown_event():
    global simulation_running
    simulation_running = False

@app.get("/metrics")
async def get_metrics():
    return {
        "queue_sizes": {
            "to_frontend": to_frontend_queue.size(),
            "from_frontend": from_frontend_queue.size(),
            "to_backend": to_backend_queue.size(),
            "from_backend": from_backend_queue.size(),
            "dead_letter": dead_letter_queue.size()
        },
        "websocket_connections": len(app.state.websockets),
        "timestamp": time.time()
    }

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
    except Exception as e:
        logging.error(f"WebSocket initial accept failed: {e}")
        return
    
    try:
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
    
    # Store active tasks for this connection
    connection_tasks = {
        'sender': asyncio.create_task(send_messages(websocket)),
        'receiver': asyncio.create_task(receive_messages(websocket))
    }
    
    try:
        done, pending = await asyncio.wait(
            [connection_tasks['sender'], connection_tasks['receiver']],
            return_when=asyncio.FIRST_COMPLETED
        )
    except asyncio.CancelledError:
        logging.info("WebSocket tasks cancelled normally")
    except Exception as e:
        logging.error(f"WebSocket error: {e}")
    finally:
        try:
            if websocket in app.state.websockets:
                app.state.websockets.remove(websocket)
            if hasattr(app.state, 'websocket_ack_status') and websocket in app.state.websocket_ack_status:
                del app.state.websocket_ack_status[websocket]
                
            if not connection_tasks['sender'].done():
                connection_tasks['sender'].cancel()
                await connection_tasks['sender']
            if not connection_tasks['receiver'].done():
                connection_tasks['receiver'].cancel()
                await connection_tasks['receiver']
                
            if websocket.client_state != 3:  # CLOSED
                await websocket.close()
                
            logging.info(f"WebSocket connection closed for {websocket.client}")
        except Exception as e:
            logging.error(f"Error during WebSocket cleanup: {e}", exc_info=True)

async def process_messages():
    """Process messages through the full pipeline with blocking behavior"""
    print("\nStarting blocking message processor pipeline...")
    while True:
        try:
            # Block until we get a message from to_backend_queue
            print(f"\n[Processor] Waiting for message in to_backend_queue...")
            backend_msg = await to_backend_queue.dequeue()
            
            try:
                validated_msg = QueueMessage(**backend_msg)
                backend_msg = validated_msg.dict()
            except ValidationError as e:
                logging.error(f"Invalid message format: {e}", exc_info=True)
                continue
                
            if backend_msg:
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
            
            # Process message and send to from_backend_queue
            backend_msg['status'] = 'processed'
            backend_msg['processing_path'].append({
                'stage': 'processing_complete',
                'timestamp': time.time()
            })
            # Process message and send to from_backend_queue
            backend_msg['status'] = 'processed'
            backend_msg['processing_path'].append({
                'stage': 'processing_complete',
                'timestamp': time.time()
            })
            await from_backend_queue.enqueue(backend_msg)
            
            # Create frontend message
            frontend_msg = {
                'type': 'frontend_update',
                'data': backend_msg,
                'timestamp': time.time()
            }
            await to_frontend_queue.enqueue(frontend_msg)
            logging.info(f"Processed and forwarded message: {backend_msg['data']['id']}")
            
            # Default processing for other messages
            await asyncio.sleep(1)
            backend_msg['status'] = 'processed'
            backend_msg['timestamp'] = time.time()
            await from_backend_queue.enqueue(backend_msg)
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
            msg = await from_backend_queue.dequeue()  # Async wait for message
            
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
            
            if msg is None:
                logging.warning("Received None message in forward_messages")
                continue
                
            await to_frontend_queue.enqueue(msg)
            logging.debug(f"Forwarded message {msg['data']['id']} to frontend")

            # Forward messages from frontend to backend
            frontend_msg = await from_frontend_queue.dequeue()
            frontend_msg['status'] = 'new_for_backend'
            await to_backend_queue.enqueue(frontend_msg)

            await asyncio.sleep(0.1)
        except Exception as e:
            print(f"Error in queue forwarding: {e}")
            await asyncio.sleep(1)

async def send_messages(websocket: WebSocket):
    """Send messages from to_frontend_queue to client"""
    client = websocket.client
    client_info = f"{client.host}:{client.port}" if client else "unknown client"
    logging.info(f"Starting sender task for {client_info}")
    
    try:
        while True:
            try:
                # Get message with timeout to prevent hanging
                try:
                    message = await asyncio.wait_for(
                        to_frontend_queue.dequeue(),
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue
                
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
                    # Prepare and send message
                    message['status'] = 'sent_to_frontend'
                    message['timestamp'] = time.time()
                    msg_str = json.dumps(message)
                    
                    try:
                        await websocket.send_text(msg_str)
                        logging.info(f"Sent message {message.get('data', {}).get('id')} to {client_info}")
                    except websockets.exceptions.ConnectionClosed:
                        logging.info(f"Connection closed while sending to {client_info}")
                        break
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
    except asyncio.CancelledError:
        logging.info(f"Sender task for {client_info} cancelled normally")
    except Exception as e:
        logging.error(f"Sender task for {client_info} failed: {e}", exc_info=True)
    finally:
        logging.info(f"Sender task for {client_info} ending")
        # Ensure any remaining messages are processed
        while to_frontend_queue.size() > 0:
            try:
                message = await to_frontend_queue.dequeue()
                logging.info(f"Processing remaining message: {message.get('data', {}).get('id')}")
            except Exception as e:
                logging.error(f"Error processing remaining message: {e}")

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
        await to_frontend_queue.enqueue(system_msg)
        
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
                    
                # Initialize ack tracking if needed
                if not hasattr(app.state, 'websocket_ack_status'):
                    app.state.websocket_ack_status = {}
                
                # Send connection ack on first message if not already sent
                if not app.state.websocket_ack_status.get(websocket, False):
                    await websocket.send_text(json.dumps({
                        'type': 'connection_ack',
                        'status': 'connected',
                        'timestamp': time.time()
                    }))
                    app.state.websocket_ack_status[websocket] = True
                if client:
                    logging.debug(f"Received from {client.host}:{client.port}: {data[:200]}...")
                else:
                    logging.debug(f"Received from an unknown client: {data[:200]}...")
                message = json.loads(data)
                # Mark as received from frontend
                if not message.get('status'):
                    message['status'] = 'received_from_frontend'
                message['timestamp'] = time.time()
                await from_frontend_queue.enqueue(message)
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
        # Clean up ack status
        if hasattr(app.state, 'websocket_ack_status') and websocket in app.state.websocket_ack_status:
            del app.state.websocket_ack_status[websocket]
