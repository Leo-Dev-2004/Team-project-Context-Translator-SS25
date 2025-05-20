from fastapi import FastAPI, WebSocket, BackgroundTasks
import asyncio
import random
from fastapi.middleware.cors import CORSMiddleware
from Backend.QueueManager.shared_queue import (
    to_frontend_queue,
    from_frontend_queue,
    to_backend_queue,
    from_backend_queue
)
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
    
    # Initial system message
    system_msg = {
        "type": "system",
        "message": "Simulation started",
        "timestamp": time.time()
    }
    print(f"\nEnqueuing initial system message: {system_msg}")
    to_backend_queue.enqueue(system_msg)
    print(f"to_backend_queue size: {to_backend_queue.size()}")
    counter = 0
    print("Simulation started - generating test entries")
    logging.info("Simulation STARTED - Generating test entries")
    
    # Initial system message
    system_msg = {
        "type": "system",
        "data": {
            "id": "sys_init",
            "message": "Simulation started",
            "status": "info"
        },
        "timestamp": time.time()
    }
    to_frontend_queue.enqueue(system_msg)
    logging.info(f"Enqueued system message: {system_msg}")

    # Start generating simulation messages
    while simulation_running:
        counter += 1
        await asyncio.sleep(1)  # Generate messages every second
        
        # Create simulation message
        sim_msg = {
            "type": "simulation",
            "data": {
                "id": f"sim_{counter}",
                "message": f"Simulation message {counter}",
                "status": "pending",
                "progress": counter % 100
            },
            "timestamp": time.time()
        }
        
        # Queue to backend for processing
        to_backend_queue.enqueue(sim_msg)
        logging.info(f"Enqueued simulation message {counter} to backend")
    
    while simulation_running:
        counter += 1
        await asyncio.sleep(1)  # Faster generation
        
        # Generate different types of messages
        msg_type = "message" if counter % 2 else "alert"
        status = "pending" if counter % 3 else "urgent"
        
        entry = {
            "id": str(counter),
            "type": msg_type,
            "data": f"{msg_type} entry {counter} - {['low','medium','high','critical'][counter % 4]} priority",
            "timestamp": time.time(),
            "status": status,
            "priority": counter % 5,
            "color": f"hsl({counter * 30 % 360}, 70%, 80%)"
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
    logging.info(f"WebSocket connection request from {client.host}:{client.port}")
    
    # Set fast timeout for initial handshake
    websocket._timeout = 5.0
    
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
        
        logging.info(f"WebSocket connection established with {client.host}:{client.port}")
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
    """Process messages through the full pipeline"""
    print("\nStarting message processor pipeline...")
    while True:
        try:
            # Process to_backend_queue -> from_backend_queue
            print(f"\n[Processor] Checking to_backend_queue (size: {to_backend_queue.size()})...")
            backend_msg = to_backend_queue.dequeue(timeout=1.0)
            if backend_msg:
                print(f"\n[Processor] Processing backend message: {backend_msg}")
                
                # Add processing status
                processing_msg = {
                    **backend_msg,
                    "status": "processing",
                    "timestamp": time.time()
                }
                from_backend_queue.enqueue(processing_msg)
                print(f"Forwarded to from_backend_queue (size: {from_backend_queue.size()})")

                # Simulate processing delay
                await asyncio.sleep(1)

                # Mark as processed
                processed_msg = {
                    **processing_msg,
                    "status": "processed", 
                    "timestamp": time.time()
                }
                to_frontend_queue.enqueue(processed_msg)
                print(f"Forwarded to to_frontend_queue (size: {to_frontend_queue.size()})")
                
                # Ensure all messages get routed to frontend
                if message.get('type') in ('simulation', 'test_message', 'system'):
                    # Convert to frontend format
                    frontend_msg = {
                        'type': 'frontend_update',
                        'data': message,
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
                            **message,
                            "data": {
                                **message.get('data', {}),
                                "status": "processing",
                                "progress": progress
                            },
                            "timestamp": time.time()
                        }
                        from_backend_queue.enqueue(update_msg)
                    
                    # Final processed message
                    message['status'] = 'processed'
                    message['timestamp'] = time.time()
                    message['data']['progress'] = 100
                    from_backend_queue.enqueue(message)
                    logging.info(f"Simulation message processed: {message}")
                else:
                    # Default processing for other messages
                    await asyncio.sleep(1)
                    message['status'] = 'processed'
                    message['timestamp'] = time.time()
                    from_backend_queue.enqueue(message)
                    logging.info(f"Message processed: {message}")
                
        except Exception as e:
            logging.error(f"Error processing message: {e}")
            await asyncio.sleep(1)

async def forward_messages():
    """Forward messages between queues"""
    while True:
        try:
            # Forward from_frontend_queue -> to_backend_queue
            if from_frontend_queue.size() > 0:
                frontend_msg = from_frontend_queue.dequeue()
                if frontend_msg:
                    to_backend_queue.enqueue(frontend_msg)
                    print(f"Forwarded from frontend to backend queue (size: {to_backend_queue.size()})")

            # Forward from_backend_queue -> to_frontend_queue 
            if from_backend_queue.size() > 0:
                backend_msg = from_backend_queue.dequeue()
                if backend_msg:
                    to_frontend_queue.enqueue(backend_msg)
                    print(f"Forwarded from backend to frontend queue (size: {to_frontend_queue.size()})")

            await asyncio.sleep(0.1)
        except Exception as e:
            print(f"Error in queue forwarding: {e}")
            await asyncio.sleep(1)

async def send_messages(websocket: WebSocket):
    """Send messages from to_frontend_queue to client"""
    client = websocket.client
    try:
        while True:
            try:
                message = to_frontend_queue.dequeue(timeout=1.0)
                if message:
                    try:
                        msg_str = json.dumps(message)
                        logging.debug(f"Sending to {client.host}:{client.port}: {msg_str[:200]}...")
                        await websocket.send_text(msg_str)
                    except RuntimeError as e:
                        if "disconnect" in str(e):
                            logging.info("WebSocket disconnected during send")
                            break
                        raise
                    except Exception as e:
                        logging.error(f"Failed to send message: {e}")
                        from_frontend_queue.enqueue(message)  # Requeue if failed
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
    """Get simulation status"""
    return {
        "running": simulation_running,
        "to_frontend_queue_size": to_frontend_queue.size(),
        "from_frontend_queue_size": from_frontend_queue.size(),
        "to_backend_queue_size": to_backend_queue.size(),
        "from_backend_queue_size": from_backend_queue.size()
    }

@app.get("/queues/debug")
async def debug_queues():
    """Debug endpoint to show queue contents"""
    def get_queue_contents(queue):
        try:
            # For MessageQueue implementation
            if hasattr(queue, '_queue'):
                return list(queue._queue)
            # For deque implementation
            elif hasattr(queue, 'copy'):
                return list(queue.copy())
            return []
        except Exception as e:
            return [f"Error: {str(e)}"]
    
    return {
        "to_frontend_queue": get_queue_contents(to_frontend_queue),
        "from_frontend_queue": get_queue_contents(from_frontend_queue),
        "to_backend_queue": get_queue_contents(to_backend_queue),
        "from_backend_queue": get_queue_contents(from_backend_queue)
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
                if not hasattr(websocket, '_connection_ack_sent'):
                    await websocket.send_text(json.dumps({
                        'type': 'connection_ack',
                        'status': 'connected',
                        'timestamp': time.time()
                    }))
                    websocket._connection_ack_sent = True
                logging.debug(f"Received from {client.host}:{client.port}: {data[:200]}...")
                message = json.loads(data)
                from_frontend_queue.enqueue(message)
                
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
