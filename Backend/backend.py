# Backend/backend.py
import asyncio
import logging
import uuid
import time
from typing import Optional, Set, cast
from starlette.websockets import WebSocketDisconnect, WebSocketState 

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

# Import the shared queue functions
from Backend.models.UniversalMessage import UniversalMessage # Ensure UniversalMessage is correctly imported

from Backend.queues.QueueTypes import AbstractMessageQueue # <<< ADD THIS IMPORT

from Backend.core.Queues import queues # Access the pre-initialized queues
from Backend.queues.MessageQueue import MessageQueue # For type hinting

# Import the SimulationManager class (for type hinting and instantiation)
from Backend.core.SimulationManager import SimulationManager

# Import BackendServiceDispatcher directly
from Backend.core.BackendServiceDispatcher import BackendServiceDispatcher

# Import WebSocketManager
from Backend.services.WebSocketManager import WebSocketManager

# Import the API router 
from .api import endpoints

# Import the functions to set and get instances from dependencies.py
from Backend.dependencies import (
    set_simulation_manager_instance, 
    get_simulation_manager, 
    set_websocket_manager_instance, 
    get_websocket_manager_instance
)

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
# This set might become redundant if WebSocketManager exclusively manages connections.
# Keep it for now if other parts of your app might still rely on it for direct WebSocket access.
app.state.websockets = set() 

# --- GLOBAL INSTANCES for Background Tasks ---
# These will be set during the startup event
message_processor_task: Optional[asyncio.Task] = None
# queue_forwarder_task: Optional[asyncio.Task] = None # REMOVED
queue_status_sender_task: Optional[asyncio.Task] = None

message_processor_instance: Optional[BackendServiceDispatcher] = None # Changed type hint
# queue_forwarder_instance: Optional[QueueForwarder] = None # REMOVED
simulation_manager_instance: Optional[SimulationManager] = None
websocket_manager_instance: Optional[WebSocketManager] = None


async def send_queue_status_to_frontend():
    # Wait a bit for initial connection and setup to complete
    await asyncio.sleep(5)
    while True:
        try:
            # Use AbstractMessageQueue for consistent typing
            incoming_q: AbstractMessageQueue = queues.incoming
            websocket_out_q: AbstractMessageQueue = queues.websocket_out
            dead_letter_q: AbstractMessageQueue = queues.dead_letter

            incoming_q_size = incoming_q.qsize()
            websocket_out_q_size = websocket_out_q.qsize()
            dead_letter_q_size = dead_letter_q.qsize()

            status_message_data = {
                "incoming_q_size": incoming_q_size,
                "websocket_out_q_size": websocket_out_q_size,
                "dead_letter_q_size": dead_letter_q_size,
            }

            # --- USE UNIVERSALMESSAGE DIRECTLY FOR QUEUE STATUS ---
            # Remove the problematic try-except block and dynamic class definition.
            # Create a UniversalMessage instance with all required fields.

            # Get the WebSocketManager instance
            # Assuming you have a get_websocket_manager_instance() function or similar
            # If not, ensure _global_ws_manager_instance is set elsewhere before this task starts.
            websocket_manager_instance: Optional[WebSocketManager] = get_websocket_manager_instance()

            if websocket_manager_instance and websocket_manager_instance.connections: # Changed .connections to .active_connections based on common pattern
                for client_id_str in list(websocket_manager_instance.connections.keys()):
                    try:
                        # Construct a UniversalMessage for the queue status update
                        queue_status_universal_message = UniversalMessage(
                            id=str(uuid.uuid4()),
                            type="system.queue_status_update",
                            origin="backend.system_monitor",
                            destination="frontend",
                            timestamp=time.time(),
                            client_id=client_id_str, # Target a specific client if needed
                            payload=status_message_data,
                            processing_path=[], # Initialize empty if not relevant here
                            # forwarding_path will be added by the WebSocketManager if it forwards
                        )

                        # Assuming WebSocketManager has a method to send a UniversalMessage to a specific client.
                        # This is the ideal way to encapsulate the sending logic.
                        if hasattr(websocket_manager_instance, 'send_universal_message_to_client'):
                            await websocket_manager_instance.send_message_to_client(client_id_str, queue_status_universal_message)
                            logger.debug(f"Sent queue status (UniversalMessage) to client {client_id_str}")
                        elif websocket_manager_instance.connections.get(client_id_str):
                            # Fallback: Directly send as JSON via WebSocket if no higher-level method
                            await websocket_manager_instance.connections[client_id_str].send_text(
                                queue_status_universal_message.model_dump_json() # Use model_dump_json for Pydantic models
                            )
                            logger.debug(f"Sent queue status directly via WS (JSON) to {client_id_str}")
                        else:
                            logger.warning(f"No suitable method or active connection for {client_id_str} to send queue status.")

                    except Exception as client_send_error:
                        logger.error(f"Error sending queue_status_update to client {client_id_str}: {client_send_error}", exc_info=True)

        except Exception as e:
            logger.error(f"Error in send_queue_status_to_frontend task: {e}", exc_info=True)
        await asyncio.sleep(1) # Send status every second
# --- FASTAPI APPLICATION STARTUP EVENT ---
@app.on_event("startup")
async def startup_event():
    logger.info("Application startup event triggered.")

    # 1. Queues are generally initialized upon import of Backend.core.Queues.
    # The explicit `initialize_and_assert_queues` is removed.
    # Just ensure that the queues are indeed populated at this point.
    if not all([queues.incoming, queues.outgoing, queues.websocket_out, queues.dead_letter]):
        raise RuntimeError("One or more critical queues failed to initialize upon import.")
    logger.info("Queues confirmed as initialized.")

    # 2. Initialize WebSocketManager instance first
    global websocket_manager_instance
    # WebSocketManager handles both incoming from WS and outgoing to WS.
    # It needs access to both incoming_queue (for messages from clients)
    # and websocket_out_queue (for messages to clients).
    websocket_manager_instance = WebSocketManager(
        incoming_queue=cast(MessageQueue, queues.incoming),
        websocket_out_queue=cast(MessageQueue, queues.websocket_out), # Pass this queue for sending
        dead_letter_queue=cast(MessageQueue, queues.dead_letter) # Pass DLQ for errors
    )
    set_websocket_manager_instance(websocket_manager_instance)
    logger.info("WebSocketManager initialized and stored in dependencies.")
    await websocket_manager_instance.start() # Ensure the manager's internal loops are running

    # 3. Initialize the SimulationManager with all required queues
    global simulation_manager_instance
    simulation_manager_instance = SimulationManager(
        incoming_queue=cast(MessageQueue, queues.incoming),
        outgoing_queue=cast(MessageQueue, queues.outgoing),
        websocket_out_queue=cast(MessageQueue, queues.websocket_out), # Simulation might send to WS
        dead_letter_queue=cast(MessageQueue, queues.dead_letter)
    )
    simulation_manager_instance.is_ready = True
    set_simulation_manager_instance(simulation_manager_instance)
    logger.info("SimulationManager initialized and stored in dependencies.")

    # 4. Initialize and start long-running background processors
    global message_processor_task, queue_status_sender_task
    global message_processor_instance

    # BackendServiceDispatcher (formerly MessageProcessor)
    # The dispatcher should use the `outgoing` queue for messages processed for external systems.
    # And `websocket_out` for messages specifically destined for the frontend.
    message_processor_instance = BackendServiceDispatcher(
        incoming_queue=cast(MessageQueue, queues.incoming),
        outgoing_queue=cast(MessageQueue, queues.outgoing), # For sending processed messages to other backend services
        websocket_out_queue=cast(MessageQueue, queues.websocket_out), # For sending processed messages to frontend
        dead_letter_queue=cast(MessageQueue, queues.dead_letter)
    )
    assert message_processor_instance is not None
    await message_processor_instance.initialize() # If your dispatcher has an initialize method
    await message_processor_instance.start() # Assuming BackendServiceDispatcher has a start method
    
    # BackendServiceDispatcher's internal processing task, if it has one
    if hasattr(message_processor_instance, '_processing_task') and message_processor_instance._processing_task:
        message_processor_task = message_processor_instance._processing_task
        logger.info("BackendServiceDispatcher's processing task started.")
    else:
        logger.warning("BackendServiceDispatcher did not expose an internal processing task or it was not set.")


    # Monitor Dead Letter Queue (task associated with BackendServiceDispatcher, if it handles it)
    # If the dispatcher has a method to monitor the DLQ for re-processing, keep this.
    # Otherwise, it might be handled elsewhere or not needed.
    assert message_processor_instance is not None
    if hasattr(message_processor_instance, 'monitor_dead_letter_queue_task'):
        asyncio.create_task(message_processor_instance.monitor_dead_letter_queue_task())
        logger.info("Background task 'monitor_dead_letter_queue_task' launched via BackendServiceDispatcher.")
    else:
        logger.info("BackendServiceDispatcher does not have a 'monitor_dead_letter_queue_task'.")

    # Start the queue status sender task and store its reference
    queue_status_sender_task = asyncio.create_task(send_queue_status_to_frontend())
    logger.info("Background task 'send_queue_status_to_frontend' launched.")


# --- FASTAPI APPLICATION SHUTDOWN EVENT ---
@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Application shutdown event triggered.")

    global message_processor_instance, simulation_manager_instance, websocket_manager_instance
    global message_processor_task, queue_status_sender_task

    # 1. Cancel the queue status sender task first
    if queue_status_sender_task:
        logger.info("Cancelling queue_status_sender_task...")
        queue_status_sender_task.cancel()
        try:
            await asyncio.wait_for(queue_status_sender_task, timeout=1.0)
        except asyncio.CancelledError:
            logger.info("queue_status_sender_task cancelled gracefully.")
        except asyncio.TimeoutError:
            logger.warning("queue_status_sender_task did not stop cleanly within timeout.")
    else:
        logger.warning("queue_status_sender_task not found for graceful shutdown.")

    # 2. Stop the simulation if it's running
    if simulation_manager_instance:
        try:
            if hasattr(simulation_manager_instance, 'is_running') and simulation_manager_instance.is_running:
                await simulation_manager_instance.stop()
                logger.info("SimulationManager explicitly stopped.")
            elif hasattr(simulation_manager_instance, 'stop'): 
                await simulation_manager_instance.stop()
                logger.info("SimulationManager stop method called.")
        except Exception as e:
            logger.error(f"Error during SimulationManager shutdown: {e}", exc_info=True)
    else:
        logger.warning("SimulationManager instance not available for graceful shutdown.")

    # 3. Stop the BackendServiceDispatcher (formerly MessageProcessor)
    if message_processor_instance: 
        logger.info("Stopping BackendServiceDispatcher...")
        try:
            await message_processor_instance.stop() 
            if message_processor_task and not message_processor_task.done():
                message_processor_task.cancel()
                try:
                    await asyncio.wait_for(message_processor_task, timeout=2.0)
                except asyncio.CancelledError:
                    logger.info("BackendServiceDispatcher task cancelled gracefully.")
                except asyncio.TimeoutError:
                    logger.warning("BackendServiceDispatcher task did not stop cleanly within timeout.")
        except Exception as e:
            logger.error(f"Error stopping BackendServiceDispatcher: {str(e)}", exc_info=True)
    else:
        logger.warning("BackendServiceDispatcher instance not available or not initialized for graceful shutdown.")

    # 4. Shutdown WebSocketManager (to close all connections managed by it)
    if websocket_manager_instance:
        logger.info("Shutting down WebSocketManager (closing all client connections)...")
        try:
            # Assuming WebSocketManager has a stop() or shutdown() method that handles its _running flag and tasks.
            await websocket_manager_instance.stop() 
            logger.info("WebSocketManager shutdown complete.")
        except Exception as e:
            logger.error(f"Error during WebSocketManager shutdown: {e}", exc_info=True)
    else:
        logger.warning("WebSocketManager instance not available for graceful shutdown.")

    # 5. Clear app.state.websockets as a final cleanup (if still used)
    remaining_websockets_count = len(app.state.websockets)
    if remaining_websockets_count > 0:
        logger.warning(f"{remaining_websockets_count} WebSocket connections still present in app.state.websockets. Attempting to force close.")
        for ws in list(app.state.websockets):
            try:
                if ws.client_state == WebSocketState.CONNECTED:
                    await ws.close(code=1001, reason="Server shutting down")
                    client_info = f"{ws.client.host}:{ws.client.port}" if ws.client else "unknown"
                    logger.debug(f"Forcibly closed WebSocket connection from app.state.websockets: {client_info}")
                else:
                    client_info = f"{ws.client.host}:{ws.client.port}" if ws.client else "unknown"
                    logger.debug(f"WebSocket already closed/disconnected in app.state.websockets: {client_info}")
            except RuntimeError as e:
                logger.warning(f"RuntimeError closing WebSocket during shutdown (likely already closed): {e}")
            except Exception as e:
                logger.error(f"Unexpected error during WebSocket force close in shutdown: {e}", exc_info=True)
            finally:
                app.state.websockets.discard(ws)

    logger.info(f"All WebSocket connections managed by WebSocketManager and app.state.websockets should be closed. Remaining in app.state.websockets: {len(app.state.websockets)}")
    logger.info("Application shutdown complete.")

# --- WebSocket Endpoint ---
@app.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    logger.info(f"Incoming WebSocket connection for client_id: {client_id}")
    app.state.websockets.add(websocket) # Keep if you still rely on this for general tracking

    if websocket_manager_instance:
        try:
            await websocket_manager_instance.handle_connection(websocket, client_id)
        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected for client_id: {client_id}")
        except Exception as e:
            logger.error(f"Error handling WebSocket connection for client_id {client_id}: {e}", exc_info=True)
        finally:
            app.state.websockets.discard(websocket) # Clean up from general tracking set
            logger.info(f"WebSocket connection for client_id {client_id} cleaned up from app.state.websockets.")
    else:
        logger.error("WebSocketManager not initialized when a connection attempted. Closing connection.")
        await websocket.close(code=1011, reason="Server internal error: WebSocketManager not ready.")


# --- Main execution block (for direct script execution with Uvicorn) ---
if __name__ == "__main__":
    import uvicorn
    logger.info("Running backend.py directly with Uvicorn.")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")