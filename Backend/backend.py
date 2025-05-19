from fastapi import FastAPI, WebSocket
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

app = FastAPI()

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

async def receive_messages(websocket: WebSocket):
    """Receive messages from client and add to from_frontend_queue"""
    while True:
        try:
            data = await websocket.receive_text()
            message = json.loads(data)
            from_frontend_queue.enqueue(message)
        except Exception as e:
            logging.error(f"Failed to process message: {e}")
