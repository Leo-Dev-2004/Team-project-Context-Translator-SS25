import logging
import asyncio
import json
import time
from typing import Optional, Dict

from fastapi import FastAPI, Depends, WebSocket, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import websockets

from .queues.shared_queue import (
    MessageQueue,
    get_initialized_queues,
    get_to_backend_queue,
    get_from_backend_queue,
    get_to_frontend_queue,
    get_from_frontend_queue,
    get_dead_letter_queue
)
from ..models.message_types import QueueMessage
from pydantic import ValidationError

from .core.simulator import SimulationManager
from .core.message_processor import MessageProcessor
from .core.queue_forwarder import QueueForwarder
from .api import endpoints

# Application-wide logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('backend.log')
    ]
)
logger = logging.getLogger(__name__)

# FastAPI application instance
app = FastAPI()

# Application state for WebSockets
app.state.websockets = set()

# Global instances for services
sim_manager_instance: Optional[SimulationManager] = None
message_processor_task: Optional[asyncio.Task] = None
queue_forwarder_task: Optional[asyncio.Task] = None

@app.on_event("startup")
async def startup_event():
    global sim_manager_instance, message_processor_task, queue_forwarder_task
    
    logger.info("Application startup event triggered")

    # Initialize all shared queues
    await get_initialized_queues()
    logger.info("Shared queues initialized")

    # Get queue instances
    to_backend_q = get_to_backend_queue()
    from_backend_q = get_from_backend_queue()
    to_frontend_q = get_to_frontend_queue()
    from_frontend_q = get_from_frontend_queue()

    # Initialize SimulationManager
    sim_manager_instance = SimulationManager(
        to_backend_queue=to_backend_q,
        to_frontend_queue=to_frontend_q,
        from_backend_queue=from_backend_q
    )
    logger.info("SimulationManager initialized")

    # Start MessageProcessor
    message_processor = MessageProcessor()
    message_processor_task = asyncio.create_task(message_processor.process())
    logger.info("MessageProcessor task started")

    # Start QueueForwarder
    queue_forwarder = QueueForwarder()
    queue_forwarder_task = asyncio.create_task(queue_forwarder.forward())
    logger.info("QueueForwarder task started")

    logger.info("Application startup complete")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Application shutdown event triggered")

    # Stop SimulationManager if running
    if sim_manager_instance and sim_manager_instance.running:
        await sim_manager_instance.stop()
        logger.info("SimulationManager stopped")

    # Cancel background tasks
    if message_processor_task and not message_processor_task.done():
        message_processor_task.cancel()
        try:
            await message_processor_task
        except asyncio.CancelledError:
            logger.info("MessageProcessor task cancelled")

    if queue_forwarder_task and not queue_forwarder_task.done():
        queue_forwarder_task.cancel()
        try:
            await queue_forwarder_task
        except asyncio.CancelledError:
            logger.info("QueueForwarder task cancelled")

    # Close WebSocket connections
    for ws in list(app.state.websockets):
        try:
            await ws.close(code=1000)
        except Exception as e:
            logger.warning(f"Error closing WebSocket: {e}")
        app.state.websockets.discard(ws)

    logger.info("Application shutdown complete")

def get_simulation_manager() -> SimulationManager:
    if sim_manager_instance is None:
        logger.error("SimulationManager not initialized")
        raise RuntimeError("SimulationManager not initialized")
    return sim_manager_instance

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:9000", "http://127.0.0.1:9000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API endpoints
app.include_router(endpoints.router)

@app.on_event("shutdown")
def shutdown_event():
    global simulation_running
    simulation_running = False



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

    print("\nStarting blocking message processor pipeline...")
    while True:
        try:
            # Block until we get a message from to_backend_queue
            print(f"\n[Processor] Waiting for message in to_backend_queue...")
            to_backend_queue = get_to_backend_queue()
            from_backend_queue = get_from_backend_queue()
            to_frontend_queue = get_to_frontend_queue()
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
    to_backend_queue = get_to_backend_queue()
    from_backend_queue = get_from_backend_queue()
    to_frontend_queue = get_to_frontend_queue()
    from_frontend_queue = get_from_frontend_queue()
    await to_backend_queue.clear()
    await from_backend_queue.clear()
    await to_frontend_queue.clear()
    await from_frontend_queue.clear()
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
