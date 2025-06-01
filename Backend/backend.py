import logging
import asyncio
import uuid
import time # Ensure time is imported if used in commented out sections or elsewhere
from typing import Optional, Dict, Set, Any

from fastapi import FastAPI, Depends, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from starlette.websockets import WebSocketDisconnect # Import WebSocketDisconnect here

# Import the shared queue functions
from Backend.queues.shared_queue import (
    get_initialized_queues,
    get_to_backend_queue,
    get_from_backend_queue,
    get_to_frontend_queue,
    get_from_frontend_queue,
    get_dead_letter_queue,
)

# Import the SimulationManager class (for type hinting and instantiation)
from Backend.core.simulator import SimulationManager

# Import MessageProcessor and QueueForwarder
from Backend.core.message_processor import MessageProcessor
from Backend.core.queue_forwarder import QueueForwarder

# ADDED: Import WebSocketManager
from Backend.services.websocket_manager import WebSocketManager # Adjust this import path if needed

# Import the API router (ensure this is from the correct relative path)
from .api import endpoints # Corrected to a relative import

# Import the functions to set and get the SimulationManager instance from dependencies.py
from Backend.dependencies import set_simulation_manager_instance, get_simulation_manager, set_websocket_manager_instance

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
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:9000",
        "http://127.0.0.1:9000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# --- INCLUDE API ROUTERS ---
app.include_router(endpoints.router)

# --- APPLICATION STATE ---
# app.state.websockets = set() # This line is kept as you provided it,
                               # but note that WebSocketManager now handles active connections internally.
                               # If this 'app.state.websockets' is used elsewhere for general tracking, keep it.
                               # For connection management, prefer the WebSocketManager's internal state.
app.state.websockets = set() # Corrected type hint for Pylance

# --- GLOBAL INSTANCES for Background Tasks ---
# These will be set during the startup event
message_processor_task: Optional[asyncio.Task] = None
queue_forwarder_task: Optional[asyncio.Task] = None
simulation_manager_task: Optional[asyncio.Task] = None

message_processor_instance: Optional[MessageProcessor] = None
queue_forwarder_instance: Optional[QueueForwarder] = None
simulation_manager_instance: Optional[SimulationManager] = None
# ADDED: Declare global WebSocketManager instance
websocket_manager_instance: Optional[WebSocketManager] = None

# --- NEW: BACKGROUND TASK TO SEND QUEUE STATUS TO FRONTEND ---
async def send_queue_status_to_frontend():
    # Wait a bit for initial connection and setup to complete
    await asyncio.sleep(5)
    while True:
        try:
            # Ensure these are the correct queue instances being checked
            # Use the queues initialized during startup
            queues = await get_initialized_queues() # Or use a global `shared_queues` dict if you set one up
            from_frontend_q = queues.get("from_frontend")
            to_frontend_q = queues.get("to_frontend")
            dead_letter_q = queues.get("dead_letter") # Ensure this is also in your initialized_queues or accessible

            from_frontend_q_size = from_frontend_q.qsize() if from_frontend_q else 0
            to_frontend_q_size = to_frontend_q.qsize() if to_frontend_q else 0
            dead_letter_q_size = dead_letter_q.qsize() if dead_letter_q else 0

            status_message = {
                "id": str(uuid.uuid4()),
                "type": "queue_status",
                "data": {
                    "from_frontend_q_size": from_frontend_q_size,
                    "to_frontend_q_size": to_frontend_q_size,
                    "dead_letter_q_size": dead_letter_q_size,
                },
                "timestamp": time.time(),
                "client_id": None, # This message is generic for all clients
                "processing_path": [],
                "forwarding_path": [],
            }

            if websocket_manager_instance and websocket_manager_instance.connections:
                logger.info(f"Attempting to send queue_status. Active connections: {len(websocket_manager_instance.connections)}")
                # CORRECTED ITERATION: Iterate over the dictionary's keys explicitly.
                # The previous version 'for client_id in websocket_manager_instance.connections:'
                # also iterates keys, but let's be explicit and debug.
                for client_id_str in websocket_manager_instance.connections:
                    try:
                        # Convert dict to QueueMessage (import the correct class if needed)
                        from Backend.queues.shared_queue import QueueMessage  # Adjust import path as needed
                        queue_message = QueueMessage(**status_message)
                        await websocket_manager_instance.send_message_to_client(client_id_str, queue_message)
                        logger.info(f"Sent queue_status to client {client_id_str}: {status_message['data']}")
                    except Exception as client_send_error:
                        logger.error(f"Error sending queue_status to client {client_id_str}: {client_send_error}", exc_info=True)
            else:
                logger.debug("No WebSocket connections to send queue_status to or WebSocketManager not ready.")


        except Exception as e:
            logger.error(f"Error in send_queue_status_to_frontend task: {e}", exc_info=True)
            # Consider a small delay here if errors are frequent to prevent busy-looping on errors
            # await asyncio.sleep(0.5)

        await asyncio.sleep(1) # Send status every 1 second


# --- FASTAPI APPLICATION STARTUP EVENT ---
@app.on_event("startup")
async def startup_event():
    logger.info("Application startup event triggered.")

    # 1. Initialize all shared queues
    queues = await get_initialized_queues()
    logger.info("Shared queues initialized.")

    # 2. Get queue instances
    to_backend_q = queues["to_backend"]
    from_backend_q = queues["from_backend"]
    to_frontend_q = queues["to_frontend"]
    from_frontend_q = queues["from_frontend"]
    dead_letter_q = get_dead_letter_queue()
    logger.info(f"Retrieved queue instances. Event loop ID: {id(asyncio.get_running_loop())}")

    # ADDED: Initialize WebSocketManager instance first
    global websocket_manager_instance
    websocket_manager_instance = WebSocketManager(from_frontend_queue=from_frontend_q)
    set_websocket_manager_instance(websocket_manager_instance)  # Store in dependencies
    logger.info("WebSocketManager initialized and stored in dependencies.")

    # 3. Initialize the SimulationManager with all required queues
    global simulation_manager_instance
    simulation_manager_instance = SimulationManager(
        to_backend_queue=to_backend_q,
        to_frontend_queue=to_frontend_q,
        from_backend_queue=from_backend_q,
        from_frontend_queue=from_frontend_q,
        dead_letter_queue=dead_letter_q
    )
    if not hasattr(simulation_manager_instance, 'is_ready'):
        simulation_manager_instance.is_ready = False
    simulation_manager_instance.is_ready = True
    set_simulation_manager_instance(simulation_manager_instance)
    logger.info("SimulationManager initialized and stored in dependencies.")

    # 4. Initialize and start long-running background processors
    global message_processor_task, queue_forwarder_task, simulation_manager_task
    global message_processor_instance, queue_forwarder_instance

    # MessageProcessor
    message_processor_instance = MessageProcessor()
    await message_processor_instance.initialize()
    await message_processor_instance.start()
    message_processor_task = message_processor_instance._processing_task
    logger.info("MessageProcessor task started.")

    # QueueForwarder
    # MODIFIED: Pass the newly created websocket_manager_instance
    queue_forwarder_instance = QueueForwarder(websocket_manager=websocket_manager_instance)
    await queue_forwarder_instance.initialize()
    queue_forwarder_task = asyncio.create_task(queue_forwarder_instance.forward())
    logger.info("QueueForwarder task started.")

    # If SimulationManager has a long-running 'run' or 'process_events' method:
    # simulation_manager_task = asyncio.create_task(simulation_manager_instance.run())
    # logger.info("SimulationManager background task started.")

    asyncio.create_task(message_processor_instance.monitor_dead_letter_queue_task())
    logger.info("Background task 'monitor_dead_letter_queue_task' launched.")

     # NEW: Start the queue status sender task
    queue_status_sender_task = asyncio.create_task(send_queue_status_to_frontend())
    logger.info("Background task 'send_queue_status_to_frontend' launched.")


# --- FASTAPI APPLICATION SHUTDOWN EVENT ---
@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Application shutdown event triggered.")

    global message_processor_instance, queue_forwarder_instance, simulation_manager_instance, websocket_manager_instance # ADDED websocket_manager_instance
    global message_processor_task, queue_forwarder_task, simulation_manager_task

    # 1. Stop the simulation if it's running (retrieve from dependencies)
    shutdown_sim_manager = get_simulation_manager()
    if shutdown_sim_manager:
        try:
            if hasattr(shutdown_sim_manager, 'running') and shutdown_sim_manager.running:
                await shutdown_sim_manager.stop()
                logger.info("SimulationManager stopped.")
            elif hasattr(shutdown_sim_manager, 'stop'):
                await shutdown_sim_manager.stop()
                logger.info("SimulationManager stop method called.")
        except Exception as e:
            logger.error(f"Error during SimulationManager shutdown: {e}", exc_info=True)
    else:
        logger.warning("SimulationManager instance not found in dependencies for graceful shutdown.")

    # 2. Cancel background tasks gracefully
    if message_processor_instance and isinstance(message_processor_instance, MessageProcessor):
        logger.info("Stopping MessageProcessor...")
        try:
            await message_processor_instance.stop()
            remaining = message_processor_instance._get_input_queue_size()
            if remaining > 0:
                logger.info(f"Draining {remaining} messages from MessageProcessor's input queue.")
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
            await queue_forwarder_instance.stop()
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
                await simulation_manager_instance.stop()
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

    # ADDED: Shutdown WebSocketManager (to close all connections managed by it)
    if websocket_manager_instance:
        logger.info("Shutting down WebSocketManager...")
        try:
            await websocket_manager_instance.shutdown()
            logger.info("WebSocketManager shutdown complete.")
        except Exception as e:
            logger.error(f"Error during WebSocketManager shutdown: {e}", exc_info=True)
    else:
        logger.warning("WebSocketManager instance not available for graceful shutdown.")

    # 3. Close active WebSocket connections (This block operates on app.state.websockets)
    # This block is kept as you provided it. If app.state.websockets is purely for legacy
    # or separate tracking and not the source of truth for active connections
    # managed by WebSocketManager, this will still run. If WebSocketManager handles
    # all closing, this might become redundant.
    for ws in list(app.state.websockets):
        try:
            await ws.close(code=1000)
            logger.debug(f"Closed WebSocket connection: {ws.client.host}:{ws.client.port}")
        except RuntimeError as e:
            logger.warning(f"RuntimeError closing WebSocket during shutdown (likely already closed): {e}")
        except Exception as e:
            logger.error(f"Unexpected error during WebSocket close in shutdown: {e}", exc_info=True)
        finally:
            app.state.websockets.discard(ws)
    logger.info(f"All WebSocket connections attempted to close. Remaining: {len(app.state.websockets)}")

    logger.info("Application shutdown complete.")

# --- WebSocket Endpoint ---
# This part of the code is typically found in api/endpoints.py.
# If you intend to use it via the router, this should be removed and placed in endpoints.py.
# However, if it remains here, it will be the active endpoint.
# It now delegates connection handling to the global websocket_manager_instance.

# REMOVED the original commented-out block (which contained the full WebSocket handling logic)
# because the new active endpoint delegates to WebSocketManager.
# The previous version of this response inadvertently showed this removal.

@app.websocket("/ws/{client_id}") # Retained your original path with {client_id}
async def websocket_endpoint(websocket: WebSocket, client_id: str): # Retained client_id parameter
    # Ensure websocket_manager_instance is available after startup
    if websocket_manager_instance:
        # Pass the WebSocket and client_id to the WebSocketManager for handling
        await websocket_manager_instance.handle_connection(websocket, client_id) # MODIFIED: Pass client_id
    else:
        logger.error("WebSocketManager not initialized when a connection attempted.")
        await websocket.close(code=1011) # Internal Error


# Removed the "Background Task for Sending Messages to Frontend via WebSockets" and
# "start_frontend_sender_task" as the QueueForwarder now handles this via WebSocketManager.
# This was a logical removal from the previous version.


# --- Main execution block (for direct script execution with Uvicorn) ---
if __name__ == "__main__":
    import uvicorn
    logger.info("Running backend.py directly with Uvicorn.")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")