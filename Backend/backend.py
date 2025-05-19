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
import time

app = FastAPI()

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
    counter = 0
    while simulation_running:
        counter += 1
        entry = {
            "id": str(counter),
            "type": "simulated",
            "data": f"Test entry {counter}",
            "timestamp": time.time(),
            "status": "pending"
        }
        # Add to backend queue for processing
        to_backend_queue.enqueue(entry)
        # Also send directly to frontend for display
        to_frontend_queue.enqueue({
            "type": "simulation_update",
            "data": entry,
            "queue_sizes": {
                "to_backend": to_backend_queue.size(),
                "from_backend": from_backend_queue.size()
            }
        })
        await asyncio.sleep(3)

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
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    # Start background tasks for queue processing
    sender_task = asyncio.create_task(send_messages(websocket))
    receiver_task = asyncio.create_task(receive_messages(websocket))
    
    try:
        await asyncio.gather(sender_task, receiver_task)
    except Exception as e:
        logging.error(f"WebSocket error: {e}")
    finally:
        sender_task.cancel()
        receiver_task.cancel()

async def send_messages(websocket: WebSocket):
    """Send messages from to_frontend_queue to client"""
    while True:
        message = to_frontend_queue.dequeue(timeout=1.0)
        if message:
            try:
                await websocket.send_text(json.dumps(message))
            except Exception as e:
                logging.error(f"Failed to send message: {e}")
                from_frontend_queue.enqueue(message)  # Requeue if failed
        await asyncio.sleep(0.1)  # Prevent busy waiting

@app.get("/simulation/start")
async def start_simulation(background_tasks: BackgroundTasks):
    """Start the queue simulation"""
    global simulation_task
    if not simulation_running:
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
    while True:
        try:
            data = await websocket.receive_text()
            message = json.loads(data)
            from_frontend_queue.enqueue(message)
        except Exception as e:
            logging.error(f"Failed to process message: {e}")
