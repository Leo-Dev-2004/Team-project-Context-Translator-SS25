# Backend/backend.py
import logging
import asyncio
from typing import Optional, Dict, Set

from fastapi import FastAPI, Depends, WebSocket
from fastapi.middleware.cors import CORSMiddleware

# Import the shared queue functions
from Backend.queues.shared_queue import (
    get_initialized_queues,
    get_to_backend_queue,
    get_from_backend_queue,
    get_to_frontend_queue,
    get_from_frontend_queue
)

# Import the SimulationManager class (for type hinting and instantiation)
from Backend.core.simulator import SimulationManager

# Import MessageProcessor and QueueForwarder
from Backend.core.message_processor import MessageProcessor
from Backend.core.queue_forwarder import QueueForwarder

# Import the API router
from Backend.api import endpoints

# Import the functions to set and get the SimulationManager instance from dependencies.py
from Backend.dependencies import set_simulation_manager_instance, get_simulation_manager
from Backend.core import message_processor

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

# --- APPLICATION STATE ---
app.state.websockets = set()  # type: ignore # type: Set[WebSocket]

# --- GLOBAL INSTANCES for Background Tasks ---
# These will be set during the startup event
message_processor_task: Optional[asyncio.Task] = None
queue_forwarder_task: Optional[asyncio.Task] = None

# Global variables for background task instances
message_processor_instance: Optional[MessageProcessor] = None # NEW GLOBAL VARIABLE
queue_forwarder_instance: Optional[QueueForwarder] = None     # NEW GLOBAL VARIABLE


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
    logger.info(f"Retrieved queue instances. Event loop ID: {id(asyncio.get_running_loop())}")

    # 3. Initialize the SimulationManager
    current_sim_manager = SimulationManager(
        to_backend_queue=to_backend_q,
        to_frontend_queue=to_frontend_q,
        from_backend_queue=from_backend_q
    )
    # Store the initialized manager instance in the dependencies module
    set_simulation_manager_instance(current_sim_manager) # NEW CALL
    logger.info("SimulationManager initialized and stored in dependencies.")

    # 4. Initialize and start long-running background processors
    global message_processor_task, queue_forwarder_task
    global message_processor_instance, queue_forwarder_instance # ADDED THESE INSTANCE GLOBALS

    message_processor_instance = MessageProcessor() # Assign to the global instance variable
    await message_processor_instance.initialize()
    message_processor_task = asyncio.create_task(message_processor_instance.process())
    logger.info("MessageProcessor task started.")

    queue_forwarder_instance = QueueForwarder() # Assign to the global instance variable
    await queue_forwarder_instance.initialize()
    queue_forwarder_task = asyncio.create_task(queue_forwarder_instance.forward())
    logger.info("QueueForwarder task started.")
    
    logger.info("Application startup complete. All core services initialized.")


# --- FASTAPI APPLICATION SHUTDOWN EVENT ---
@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Application shutdown event triggered.")
    
    # 1. Stop the simulation if it's running (retrieve from dependencies)
    try:
        shutdown_sim_manager = get_simulation_manager() # Use the getter from dependencies
        if shutdown_sim_manager.running:
            await shutdown_sim_manager.stop()
            logger.info("SimulationManager stopped.")
    except RuntimeError as e:
        logger.warning(f"SimulationManager not available for graceful shutdown: {e}")

    # 2. Cancel background tasks gracefully
    global message_processor_instance, queue_forwarder_instance # Access global instance

    if message_processor_task and message_processor_instance: # Check both task and instance exist
        logger.info("Stopping MessageProcessor...")
        try:
            # Call the stop method on the GLOBAL INSTANCE
            await message_processor_instance.stop() # FIX for line 116

            if not message_processor_task.done():
                message_processor_task.cancel()
                try:
                    await asyncio.wait_for(message_processor_task, timeout=2.0)
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    logger.warning("MessageProcessor didn't stop cleanly")

                # Call get_input_queue_size on the GLOBAL INSTANCE
                remaining = message_processor_instance.get_input_queue_size() # FIX for line 126
                if remaining > 0:
                    logger.info(f"Draining {remaining} messages from input queue")
        except Exception as e:
            logger.error(f"Error stopping MessageProcessor: {str(e)}")
    else:
        logger.warning("MessageProcessor instance or task not available for graceful shutdown.")

    if queue_forwarder_task and queue_forwarder_instance and not queue_forwarder_task.done():
        queue_forwarder_task.cancel()
        try:
            await queue_forwarder_task
        except asyncio.CancelledError:
            logger.info("QueueForwarder task cancelled.")
    else:
        logger.warning("QueueForwarder instance or task not available for graceful shutdown.")

    # 3. Close active WebSocket connections
    for ws in list(app.state.websockets):
        try:
            await ws.close(code=1000)
        except RuntimeError as e:
            logger.warning(f"Error closing WebSocket during shutdown: {e}")
        except Exception as e:
            logger.error(f"Unexpected error during WebSocket close in shutdown: {e}")
        app.state.websockets.discard(ws)
    logger.info("All WebSocket connections attempted to close.")
    
    logger.info("Application shutdown complete.")


# --- FASTAPI MIDDLEWARE ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:9000", "http://127.0.0.1:9000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- INCLUDE API ROUTERS ---
from .api import endpoints  # Import nach der App-Erstellung
app.include_router(endpoints.router)
