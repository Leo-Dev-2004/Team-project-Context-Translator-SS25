import logging
import asyncio
from typing import Optional, Dict, Set, Any

from fastapi import FastAPI, Depends, WebSocket
from fastapi.middleware.cors import CORSMiddleware

# Import the shared queue functions
from Backend.queues.shared_queue import (
    get_initialized_queues,
    get_to_backend_queue,
    get_from_backend_queue,
    get_to_frontend_queue,
    get_from_frontend_queue,
    get_dead_letter_queue
)

# Import the SimulationManager class (for type hinting and instantiation)
from Backend.core.simulator import SimulationManager

# Import MessageProcessor and QueueForwarder
from Backend.core.message_processor import MessageProcessor
from Backend.core.queue_forwarder import QueueForwarder

# Import the API router (ensure this is from the correct relative path)
from .api import endpoints # Corrected to a relative import

# Import the functions to set and get the SimulationManager instance from dependencies.py
from Backend.dependencies import set_simulation_manager_instance, get_simulation_manager

# --- APPLICATION-WIDE LOGGING CONFIGURATION ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('backend.log')
    ]
)
logger = logging.getLogger(__name__)

# --- FASTAPI APPLICATION INSTANCE ---
app = FastAPI()

# --- FASTAPI MIDDLEWARE ---
# Removed duplicate origins list and consolidated `allow_origins`
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:9000",
        "http://127.0.0.1:9000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "ws://localhost:9000",
        "ws://127.0.0.1:9000"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"]
)


# --- INCLUDE API ROUTERS ---
app.include_router(endpoints.router)

# --- APPLICATION STATE ---
app.state.websockets = set() # Corrected type hint for Pylance

# --- GLOBAL INSTANCES for Background Tasks ---
# These will be set during the startup event
message_processor_task: Optional[asyncio.Task] = None
queue_forwarder_task: Optional[asyncio.Task] = None
simulation_manager_task: Optional[asyncio.Task] = None # Added for consistency if SIM has a task

# Global variables for background task instances (already correct, but adding type for consistency)
message_processor_instance: Optional[MessageProcessor] = None
queue_forwarder_instance: Optional[QueueForwarder] = None
simulation_manager_instance: Optional[SimulationManager] = None # Added for consistency

# --- FASTAPI APPLICATION STARTUP EVENT ---
@app.on_event("startup")
async def startup_event():
    logger.info("Application startup event triggered.")

    # 1. Initialize all shared queues
    queues = await get_initialized_queues()
    logger.info("Shared queues initialized.")

    # 2. Get queue instances
    # The return type of get_initialized_queues provides these,
    # so we can safely cast or rely on context
    to_backend_q = queues["to_backend"]
    from_backend_q = queues["from_backend"]
    to_frontend_q = queues["to_frontend"]
    from_frontend_q = queues["from_frontend"]
    dead_letter_q = get_dead_letter_queue()
    logger.info(f"Retrieved queue instances. Event loop ID: {id(asyncio.get_running_loop())}")

    # 3. Initialize the SimulationManager with all required queues
    global simulation_manager_instance # Declare global usage
    simulation_manager_instance = SimulationManager(
        to_backend_queue=to_backend_q,
        to_frontend_queue=to_frontend_q,
        from_backend_queue=from_backend_q,
        from_frontend_queue=from_frontend_q,
        dead_letter_queue=dead_letter_q
    )
    # The 'is_ready' attribute should ideally be part of the SimulationManager's __init__ or initialize method
    # For now, setting it directly, but consider moving it into SimulationManager's lifecycle.
    if not hasattr(simulation_manager_instance, 'is_ready'):
        simulation_manager_instance.is_ready = False # Pylance might warn if not in __init__
    simulation_manager_instance.is_ready = True # Set to True after initialization
    # Store the initialized manager instance in the dependencies module
    set_simulation_manager_instance(simulation_manager_instance)
    logger.info("SimulationManager initialized and stored in dependencies.")

    # 4. Initialize and start long-running background processors
    global message_processor_task, queue_forwarder_task, simulation_manager_task
    global message_processor_instance, queue_forwarder_instance # Ensure these are declared global

    # MessageProcessor
    message_processor_instance = MessageProcessor()
    await message_processor_instance.initialize()
    # It's better to use the 'start' method if available, as it manages its own task creation.
    # If _process_messages is the internal loop, the start method should call it.
    # Assuming MessageProcessor.start() handles creating and managing _processing_task
    await message_processor_instance.start()
    # If start() returns the task or stores it, assign it here:
    message_processor_task = message_processor_instance._processing_task # Access the internal task directly
    logger.info("MessageProcessor task started.")

    # QueueForwarder
    queue_forwarder_instance = QueueForwarder()
    await queue_forwarder_instance.initialize()
    queue_forwarder_task = asyncio.create_task(queue_forwarder_instance.forward())
    logger.info("QueueForwarder task started.")

    # If SimulationManager has a long-running 'run' or 'process_events' method:
    # simulation_manager_task = asyncio.create_task(simulation_manager_instance.run())
    # logger.info("SimulationManager background task started.")

    logger.info("Application startup complete. All core services initialized.")


# --- FASTAPI APPLICATION SHUTDOWN EVENT ---
@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Application shutdown event triggered.")

    global message_processor_instance, queue_forwarder_instance, simulation_manager_instance
    global message_processor_task, queue_forwarder_task, simulation_manager_task

    # 1. Stop the simulation if it's running (retrieve from dependencies)
    shutdown_sim_manager = get_simulation_manager() # Use the getter from dependencies
    if shutdown_sim_manager: # Ensure the manager was set
        try:
            if hasattr(shutdown_sim_manager, 'running') and shutdown_sim_manager.running:
                await shutdown_sim_manager.stop()
                logger.info("SimulationManager stopped.")
            elif hasattr(shutdown_sim_manager, 'stop'): # If 'running' attribute not present, just try stopping
                await shutdown_sim_manager.stop()
                logger.info("SimulationManager stop method called.")
        except Exception as e: # Catch any errors during sim manager stop
            logger.error(f"Error during SimulationManager shutdown: {e}", exc_info=True)
    else:
        logger.warning("SimulationManager instance not found in dependencies for graceful shutdown.")


    # 2. Cancel background tasks gracefully
    # Use explicit type checks to help Pylance
    if message_processor_instance and isinstance(message_processor_instance, MessageProcessor):
        logger.info("Stopping MessageProcessor...")
        try:
            # Call the stop method on the GLOBAL INSTANCE
            await message_processor_instance.stop() # This is now correctly typed

            # Check for remaining messages after its internal stop
            remaining = message_processor_instance._get_input_queue_size()
            if remaining > 0:
                logger.info(f"Draining {remaining} messages from MessageProcessor's input queue.")
            
            # Cancel the associated task if it exists and is still running
            if message_processor_task and not message_processor_task.done():
                message_processor_task.cancel()
                try:
                    await asyncio.wait_for(message_processor_task, timeout=2.0)
                except asyncio.CancelledError:
                    logger.info("MessageProcessor task cancelled gracefully.")
                except asyncio.TimeoutError:
                    logger.warning("MessageProcessor task did not stop cleanly within timeout.")

        except Exception as e:
            logger.error(f"Error stopping MessageProcessor: {str(e)}", exc_info=True)
    else:
        logger.warning("MessageProcessor instance not available or not initialized for graceful shutdown.")


    if queue_forwarder_instance and isinstance(queue_forwarder_instance, QueueForwarder):
        logger.info("Stopping QueueForwarder...")
        try:
            await queue_forwarder_instance.stop() # Call the stop method
            if queue_forwarder_task and not queue_forwarder_task.done():
                queue_forwarder_task.cancel()
                try:
                    await asyncio.wait_for(queue_forwarder_task, timeout=2.0)
                except asyncio.CancelledError:
                    logger.info("QueueForwarder task cancelled gracefully.")
                except asyncio.TimeoutError:
                    logger.warning("QueueForwarder task did not stop cleanly within timeout.")
        except Exception as e:
            logger.error(f"Error stopping QueueForwarder: {str(e)}", exc_info=True)
    else:
        logger.warning("QueueForwarder instance not available or not initialized for graceful shutdown.")

    if simulation_manager_instance and isinstance(simulation_manager_instance, SimulationManager):
        logger.info("Calling SimulationManager instance stop method...")
        try:
            if hasattr(simulation_manager_instance, 'stop'):
                await simulation_manager_instance.stop() # Ensure it has a stop method
            if simulation_manager_task and not simulation_manager_task.done():
                simulation_manager_task.cancel()
                try:
                    await asyncio.wait_for(simulation_manager_task, timeout=2.0)
                except asyncio.CancelledError:
                    logger.info("SimulationManager task cancelled gracefully.")
                except asyncio.TimeoutError:
                    logger.warning("SimulationManager task did not stop cleanly within timeout.")
        except Exception as e:
            logger.error(f"Error stopping SimulationManager: {str(e)}", exc_info=True)
    else:
        logger.warning("SimulationManager instance not available or not initialized for graceful shutdown.")


    # 3. Close active WebSocket connections
    # Iterate over a copy of the set as elements might be removed during iteration
    for ws in list(app.state.websockets):
        try:
            await ws.close(code=1000)
            logger.debug(f"Closed WebSocket connection: {ws.client.host}:{ws.client.port}")
        except RuntimeError as e: # This can happen if WS is already closing
            logger.warning(f"RuntimeError closing WebSocket during shutdown (likely already closed): {e}")
        except Exception as e:
            logger.error(f"Unexpected error during WebSocket close in shutdown: {e}", exc_info=True)
        finally:
            app.state.websockets.discard(ws) # Ensure it's removed
    logger.info(f"All WebSocket connections attempted to close. Remaining: {len(app.state.websockets)}")

    logger.info("Application shutdown complete.")

# --- WebSocket Endpoint ---
# This part of the code is typically found in api/endpoints.py
# If you moved it, you'll need to re-add it here or ensure it's in endpoints.py

# Placeholder for the WebSocket endpoint if it's managed directly in backend.py
# If you intend to use it via the router, this should be removed and placed in endpoints.py
"""
@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    await websocket.accept()
    app.state.websockets.add(websocket) # Add the WebSocket to the set
    logger.info(f"WebSocket connected: {client_id}. Total active: {len(app.state.websockets)}")

    # Send a welcome message
    # Ensure get_to_frontend_queue() is safe to call here (i.e., queues are initialized)
    welcome_message_dict = {
        "type": "system_info",
        "data": {"message": f"Welcome, {client_id}! Connection established."},
        "client_id": client_id
    }
    # Direct send to the client first to ensure immediate feedback
    await websocket.send_json(welcome_message_dict)
    logger.debug(f"Sent welcome message to {client_id}.")

    try:
        while True:
            data = await websocket.receive_text()
            logger.info(f"Received message from {client_id}: {data}")

            # Process incoming message through the queues
            # You might want a Pydantic model for incoming messages too
            message_for_processing = {
                "type": "raw_websocket_message",
                "data": data,
                "client_id": client_id,
                "timestamp": time.time()
            }
            # Enqueue to from_frontend_queue for processing by QueueForwarder
            from_frontend_q = get_from_frontend_queue()
            if from_frontend_q:
                await from_frontend_q.enqueue(message_for_processing)
                logger.debug(f"Enqueued raw message from {client_id} to from_frontend_queue.")
            else:
                logger.error("from_frontend_queue not initialized. Cannot enqueue message.")
                # Send error back to client
                await websocket.send_json({"type": "error", "message": "Backend not ready."})

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {client_id}. Remaining active: {len(app.state.websockets)}")
    except Exception as e:
        logger.error(f"WebSocket error for {client_id}: {e}", exc_info=True)
    finally:
        app.state.websockets.discard(websocket) # Remove from the set
        logger.info(f"Active connections after disconnect/error: {len(app.state.websockets)}")

# --- Background Task for Sending Messages to Frontend via WebSockets ---

async def send_messages_to_frontend_task():
    logger.info("Starting background task: send_messages_to_frontend_task")
    to_frontend_queue = get_to_frontend_queue() # Get the queue instance

    if not to_frontend_queue:
        logger.error("to_frontend_queue not initialized. Cannot start send_messages_to_frontend_task.")
        return

    while True:
        try:
            # Dequeue messages from the queue
            message = await to_frontend_queue.dequeue()
            if message:
                if 'client_id' in message and message['client_id'] in app.state.websockets:
                    # Find the correct WebSocket object based on client_id (this requires storing WS objects with client_ids)
                    # Currently, app.state.websockets is a Set[WebSocket], not a Dict[client_id, WebSocket]
                    # You need to adjust app.state.websockets to store client_id -> WebSocket mapping
                    # For simplicity, assuming 'message' already contains the WS object or an identifier to find it:
                    
                    # --- CRITICAL: You need to modify app.state.websockets to store a mapping ---
                    # E.g., change app.state.websockets = {} (dict) in global scope
                    # And in @app.websocket: active_connections[client_id] = websocket
                    # And use that dict here.
                    
                    # For now, let's assume `message` contains the full message as it comes from the processor,
                    # and that `active_connections` (from your previous backend.py) is the source of truth.
                    # As I don't have the full context of how `active_connections` is used in this file,
                    # I'll reintroduce it as a global for this specific send task.

                    global active_connections # Assuming this is a global dict as in your previous full backend.py
                    client_id = message.get('client_id')
                    if client_id and client_id in active_connections:
                        websocket = active_connections[client_id]
                        try:
                            await websocket.send_json(message)
                            logger.debug(f"Sent message type '{message.get('type')}' to client {client_id}.")
                        except WebSocketDisconnect:
                            logger.warning(f"Client {client_id} disconnected while sending. Removing.")
                            del active_connections[client_id]
                            app.state.websockets.discard(websocket) # Also remove from the set if used
                        except Exception as e:
                            logger.error(f"Error sending message to {client_id}: {e}", exc_info=True)
                            # Consider sending to DLQ if delivery failed
                            await get_dead_letter_queue().enqueue({
                                'original_message': message,
                                'error': 'failed_to_send_to_websocket',
                                'details': str(e),
                                'timestamp': time.time()
                            })
                    else:
                        logger.warning(f"Client {client_id} not found in active connections or message missing ID. Message dropped.")
                        await get_dead_letter_queue().enqueue({
                            'original_message': message,
                            'error': 'client_not_found_for_delivery',
                            'timestamp': time.time()
                        })
                else:
                    logger.warning(f"Message in to_frontend_queue missing 'client_id' or not a dict: {message}. Dropping.")
                    await get_dead_letter_queue().enqueue({
                        'original_message': message,
                        'error': 'invalid_message_format_for_delivery',
                        'timestamp': time.time()
                    })
            else:
                await asyncio.sleep(0.05) # Small sleep to prevent busy-waiting
        except Exception as e:
            logger.error(f"Critical error in send_messages_to_frontend_task: {e}", exc_info=True)
            await asyncio.sleep(1) # Backoff on errors

# Start this background task on application startup
@app.on_event("startup")
async def start_frontend_sender_task():
    asyncio.create_task(send_messages_to_frontend_task())
    logger.info("Background task 'send_messages_to_frontend_task' launched.")

"""


# --- Main execution block (for direct script execution with Uvicorn) ---
if __name__ == "__main__":
    import uvicorn
    # This block is for when you run `python backend.py` directly.
    # When SystemRunner.py runs `uvicorn Backend.backend:app`, this block is not executed.
    logger.info("Running backend.py directly with Uvicorn.")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")