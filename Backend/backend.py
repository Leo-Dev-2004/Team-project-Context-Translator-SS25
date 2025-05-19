from fastapi import FastAPI, WebSocket, BackgroundTasks
import asyncio
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

async def simulate_entries(websocket: WebSocket):
    """Background task to simulate queue entries"""
    global simulation_running
    simulation_running = True
    counter = 0
    print("Simulation started - generating test entries")
    
    while simulation_running:
        counter += 1
        await asyncio.sleep(3)  # Move sleep to start of loop to prevent race conditions
        
        entry = {
            "id": str(counter),
            "type": "simulated",
            "data": f"Test entry {counter}",
            "timestamp": time.time(),
            "status": "pending"
        }
        
        print(f"Generating entry {counter}: {entry}")
        
        # Send to frontend first
        frontend_msg = {
            "type": "frontend_message",
            "data": entry,
            "status": "created",
            "timestamp": time.time()
        }
        to_frontend_queue.enqueue(frontend_msg)
        
        # Then send to backend for processing
        backend_msg = {
            "type": "backend_message",
            "data": entry,
            "status": "processing",
            "timestamp": time.time()
        }
        to_backend_queue.enqueue(backend_msg)
        print(f"Sent to frontend queue (size: {to_frontend_queue.size()})")
        
        await asyncio.sleep(3)
    
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
    try:
        await websocket.accept()
        if not hasattr(app.state, 'websockets'):
            app.state.websockets = set()
        app.state.websockets.add(websocket)
        logging.info(f"WebSocket connection established with {client.host}:{client.port}")
        logging.info(f"Current WebSocket connections: {len(app.state.websockets)}")
    except Exception as e:
        logging.error(f"WebSocket accept failed: {e}")
        raise
    
    # Start background tasks for queue processing
    processor_task = asyncio.create_task(process_messages())
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
    """Process messages from backend queue"""
    while True:
        try:
            message = to_backend_queue.dequeue(timeout=1.0)
            if message:
                logging.info(f"Processing message: {message}")
                
                # Simulate processing
                await asyncio.sleep(1)
                
                # Update status
                message['status'] = 'processed'
                message['timestamp'] = time.time()
                
                # Send back to frontend
                from_backend_queue.enqueue(message)
                logging.info(f"Message processed: {message}")
                
        except Exception as e:
            logging.error(f"Error processing message: {e}")
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
        return {"status": "simulation started"}
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

async def receive_messages(websocket: WebSocket):
    """Receive messages from client and add to from_frontend_queue"""
    client = websocket.client
    try:
        while True:
            try:
                data = await websocket.receive_text()
                # Handle ping messages
                message = json.loads(data)
                if message.get('type') == 'ping':
                    await websocket.send_text(json.dumps({
                        'type': 'pong',
                        'timestamp': message['timestamp']
                    }))
                    continue
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
