# Backend/backend.py
import asyncio
import logging
import uuid
import time
from typing import Optional, Set, cast
from starlette.websockets import WebSocketDisconnect, WebSocketState # Import WebSocketState

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

# Import the shared queue functions
from Backend.models.message_types import QueueMessage, WebSocketMessage

from Backend.core.Queues import queues
from Backend.queues.MessageQueue import MessageQueue

# Import the SimulationManager class (for type hinting and instantiation)
from Backend.core.simulator import SimulationManager

# Import MessageProcessor and QueueForwarder
# ASSUMPTION: MessageProcessor.py exists directly within the BackendServiceDispatcher directory.
# If not, adjust this path.
from Backend.core.BackendServiceDispatcher.MessageProcessor import MessageProcessor
from Backend.core.queue_forwarder import QueueForwarder

# Import WebSocketManager and queue initialization
from Backend.queues.MessageQueue import initialize_and_assert_queues
from Backend.services.websocket_manager import WebSocketManager

# Import the API router (ensure this is from the correct relative path)
from .api import endpoints

# Import the functions to set and get the SimulationManager instance from dependencies.py
from Backend.dependencies import set_simulation_manager_instance, get_simulation_manager, set_websocket_manager_instance, get_websocket_manager_instance

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
app.state.websockets = set()

# --- GLOBAL INSTANCES for Background Tasks ---
# These will be set during the startup event
message_processor_task: Optional[asyncio.Task] = None
queue_forwarder_task: Optional[asyncio.Task] = None
queue_status_sender_task: Optional[asyncio.Task] = None

message_processor_instance: Optional[MessageProcessor] = None
queue_forwarder_instance: Optional[QueueForwarder] = None
simulation_manager_instance: Optional[SimulationManager] = None
websocket_manager_instance: Optional[WebSocketManager] = None


# --- BACKGROUND TASK TO SEND QUEUE STATUS TO FRONTEND ---
async def send_queue_status_to_frontend():
    # Wait a bit for initial connection and setup to complete
    await asyncio.sleep(5)
    while True:
        try:
            # Using new queue names: incoming, websocket_out, dead_letter
            # Casts are important to help Pylance understand the type after initialization
            incoming_q = cast(MessageQueue, queues.incoming)
            websocket_out_q = cast(MessageQueue, queues.websocket_out)
            dead_letter_q = cast(MessageQueue, queues.dead_letter)

            incoming_q_size = incoming_q.qsize() if incoming_q else 0
            websocket_out_q_size = websocket_out_q.qsize() if websocket_out_q else 0
            dead_letter_q_size = dead_letter_q.qsize() if dead_letter_q else 0

            status_message_data = {
                "incoming_q_size": incoming_q_size,
                "websocket_out_q_size": websocket_out_q_size,
                "dead_letter_q_size": dead_letter_q_size,
            }

            if websocket_manager_instance and websocket_manager_instance.connections:
                for client_id_str in list(websocket_manager_instance.connections.keys()):
                    try:
                        queue_message = QueueMessage(
                            id=str(uuid.uuid4()),
                            type="queue_status_update",
                            data=status_message_data,
                            timestamp=time.time(),
                            client_id=client_id_str,
                            processing_path=[],
                            forwarding_path=[],
                        )
                        # This check remains, but you must ensure the method exists in WebSocketManager
                        if hasattr(websocket_manager_instance, 'send_message_to_client'):
                            await websocket_manager_instance.send_message_to_client(client_id_str, queue_message)
                        else:
                            logger.warning(f"WebSocketManager does not have 'send_message_to_client' method. Cannot send queue status to {client_id_str}.")
                    except Exception as client_send_error:
                        logger.error(f"Error sending queue_status_update to client {client_id_str}: {client_send_error}", exc_info=True)

        except Exception as e:
            logger.error(f"Error in send_queue_status_to_frontend task: {e}", exc_info=True)
        await asyncio.sleep(1)


# --- FASTAPI APPLICATION STARTUP EVENT ---
@app.on_event("startup")
async def startup_event():
    logger.info("Application startup event triggered.")

    # 1. Initialize all shared queues
    await initialize_and_assert_queues()
    # Updated queue names for assert
    if not all([queues.incoming, queues.outgoing, queues.websocket_out, queues.dead_letter]):
        raise RuntimeError("One or more critical queues failed to initialize")
    logger.info("Queues initialized successfully.")

    # 2. Initialize WebSocketManager instance first
    global websocket_manager_instance
    # Using the new queue name: incoming
    websocket_manager_instance = WebSocketManager(
        incoming_queue=cast(MessageQueue, queues.incoming)
    )
    set_websocket_manager_instance(websocket_manager_instance)
    logger.info("WebSocketManager initialized and stored in dependencies.")

    # 3. Initialize the SimulationManager with all required queues
    global simulation_manager_instance
    # Using new, consistent queue names for SimulationManager constructor
    simulation_manager_instance = SimulationManager(
        incoming_queue=cast(MessageQueue, queues.incoming),
        outgoing_queue=cast(MessageQueue, queues.outgoing),
        websocket_out_queue=cast(MessageQueue, queues.websocket_out),
        dead_letter_queue=cast(MessageQueue, queues.dead_letter)
    )
    simulation_manager_instance.is_ready = True
    set_simulation_manager_instance(simulation_manager_instance)
    logger.info("SimulationManager initialized and stored in dependencies.")

    # 4. Initialize and start long-running background processors
    global message_processor_task, queue_forwarder_task, queue_status_sender_task
    global message_processor_instance, queue_forwarder_instance

    # MessageProcessor
    message_processor_instance = MessageProcessor()
    # Assert not None to satisfy Pylance for subsequent calls
    assert message_processor_instance is not None
    await message_processor_instance.initialize()
    await message_processor_instance.start()
    # Check if _processing_task is set before assigning
    if message_processor_instance._processing_task:
        message_processor_task = message_processor_instance._processing_task
        logger.info("MessageProcessor task started.")
    else:
        logger.error("MessageProcessor._processing_task was not set after start().")

    # QueueForwarder
    # Assert not None for websocket_manager_instance to satisfy Pylance
    assert websocket_manager_instance is not None
    queue_forwarder_instance = QueueForwarder(websocket_manager=websocket_manager_instance)
    # Assert not None for queue_forwarder_instance
    assert queue_forwarder_instance is not None
    await queue_forwarder_instance.initialize()
    queue_forwarder_task = asyncio.create_task(queue_forwarder_instance.forward())
    logger.info("QueueForwarder task started.")

    # Monitor Dead Letter Queue (task associated with MessageProcessor)
    # Assert not None for message_processor_instance before accessing its method
    assert message_processor_instance is not None
    asyncio.create_task(message_processor_instance.monitor_dead_letter_queue_task())
    logger.info("Background task 'monitor_dead_letter_queue_task' launched.")

    # Start the queue status sender task and store its reference
    queue_status_sender_task = asyncio.create_task(send_queue_status_to_frontend())
    logger.info("Background task 'send_queue_status_to_frontend' launched.")


# --- FASTAPI APPLICATION SHUTDOWN EVENT ---
@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Application shutdown event triggered.")

    global message_processor_instance, queue_forwarder_instance, simulation_manager_instance, websocket_manager_instance
    global message_processor_task, queue_forwarder_task, queue_status_sender_task

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

    # 2. Stop the simulation if it's running (use the global instance directly)
    if simulation_manager_instance:
        try:
            # Assuming SimulationManager has an 'is_running' or similar flag
            if hasattr(simulation_manager_instance, 'is_running') and simulation_manager_instance.is_running:
                await simulation_manager_instance.stop()
                logger.info("SimulationManager explicitly stopped.")
            elif hasattr(simulation_manager_instance, 'stop'): # Fallback
                await simulation_manager_instance.stop()
                logger.info("SimulationManager stop method called (via direct instance).")
        except Exception as e:
            logger.error(f"Error during SimulationManager shutdown: {e}", exc_info=True)
    else:
        logger.warning("SimulationManager instance not available for graceful shutdown.")

    # 3. Cancel other background tasks gracefully
    if message_processor_instance: # Use `if` check for Optional
        logger.info("Stopping MessageProcessor...")
        try:
            await message_processor_instance.stop() # Assuming MessageProcessor has a stop method
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

    if queue_forwarder_instance: # Use `if` check for Optional
        logger.info("Stopping QueueForwarder...")
        try:
            await queue_forwarder_instance.stop() # Assuming QueueForwarder has a stop method
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

    # 4. Shutdown WebSocketManager (to close all connections managed by it)
    if websocket_manager_instance:
        logger.info("Shutting down WebSocketManager (closing all client connections)...")
        try:
            await websocket_manager_instance.shutdown()
            logger.info("WebSocketManager shutdown complete.")
        except Exception as e:
            logger.error(f"Error during WebSocketManager shutdown: {e}", exc_info=True)
    else:
        logger.warning("WebSocketManager instance not available for graceful shutdown.")

    # 5. Clear app.state.websockets as a final cleanup
    remaining_websockets_count = len(app.state.websockets)
    if remaining_websockets_count > 0:
        logger.warning(f"{remaining_websockets_count} WebSocket connections still present in app.state.websockets. Attempting to force close.")
        for ws in list(app.state.websockets):
            try:
                if ws.client_state == WebSocketState.CONNECTED: # Corrected import for WebSocketState
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
    app.state.websockets.add(websocket)

    if websocket_manager_instance:
        try:
            await websocket_manager_instance.handle_connection(websocket, client_id)
        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected for client_id: {client_id}")
        except Exception as e:
            logger.error(f"Error handling WebSocket connection for client_id {client_id}: {e}", exc_info=True)
        finally:
            app.state.websockets.discard(websocket)
            logger.info(f"WebSocket connection for client_id {client_id} cleaned up from app.state.websockets.")
    else:
        logger.error("WebSocketManager not initialized when a connection attempted. Closing connection.")
        await websocket.close(code=1011, reason="Server internal error: WebSocketManager not ready.")


# --- Main execution block (for direct script execution with Uvicorn) ---
if __name__ == "__main__":
    import uvicorn
    logger.info("Running backend.py directly with Uvicorn.")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")