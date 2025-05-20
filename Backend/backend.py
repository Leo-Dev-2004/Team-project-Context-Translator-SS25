import logging
import asyncio
from typing import Optional, Dict, Set

from fastapi import FastAPI, Depends, WebSocket # Keep WebSocket if managing app.state.websockets
from fastapi.middleware.cors import CORSMiddleware

# --- IMPORTS FROM OTHER MODULES ---
# Import the shared queue functions and AsyncQueue class
from .queues.shared_queue import (
    MessageQueue, # Assuming MessageQueue was renamed to AsyncQueue
    get_initialized_queues,
    get_to_backend_queue,
    get_from_backend_queue,
    get_to_frontend_queue,
    get_from_frontend_queue
)

# Import the SimulationManager (from core/simulator.py)
from .core.simulator import SimulationManager

# Import the MessageProcessor (from core/message_processor.py)
from .core.message_processor import MessageProcessor

# Import the QueueForwarder (from core/queue_forwarder.py)
from .core.queue_forwarder import QueueForwarder

# Import the API router (from api/endpoints.py)
from .api import endpoints

# --- APPLICATION-WIDE LOGGING CONFIGURATION ---
# This can remain here as it configures the central application's logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('backend.log') # Ensure this path is writable
    ]
)
logger = logging.getLogger(__name__)

# --- FASTAPI APPLICATION INSTANCE ---
app = FastAPI()

# --- APPLICATION STATE ---


# --- GLOBAL INSTANCES FOR SERVICES ---
# These will be initialized during the startup event and managed by the app
sim_manager_instance: Optional[SimulationManager] = None
message_processor_task: Optional[asyncio.Task] = None
queue_forwarder_task: Optional[asyncio.Task] = None


# --- FASTAPI APPLICATION STARTUP EVENT ---
@app.on_event("startup")
async def startup_event():
    logger.info("Application startup event triggered.")

    # 1. Initialize all shared queues
    await get_initialized_queues()
    logger.info("Shared queues initialized.")

    # 2. Retrieve the initialized queue instances (using getters)
    to_backend_q = get_to_backend_queue()
    from_backend_q = get_from_backend_queue()
    to_frontend_q = get_to_frontend_queue()
    from_frontend_q = get_from_frontend_queue()
    logger.info(f"Retrieved queue instances. Event loop ID: {id(asyncio.get_running_loop())}")

    # 3. Initialize the SimulationManager, passing it the queues
    global sim_manager_instance
    sim_manager_instance = SimulationManager(
        to_backend_queue=to_backend_q,
        to_frontend_queue=to_frontend_q,
        from_backend_queue=from_backend_q
    )
    logger.info("SimulationManager initialized.")

    # 4. Initialize and start long-running background processors
    global message_processor_task, queue_forwarder_task

    # Instantiate MessageProcessor and start its main processing loop
    message_processor = MessageProcessor(
        to_backend_queue=to_backend_q,
        from_backend_queue=from_backend_q,
        to_frontend_queue=to_frontend_q # Assuming it needs to forward
    )
    message_processor_task = asyncio.create_task(message_processor.process())
    logger.info("MessageProcessor task started.")

    # Instantiate QueueForwarder and start its main forwarding loop
    queue_forwarder = QueueForwarder(
        from_backend_queue=from_backend_q,
        to_frontend_queue=to_frontend_q,
        from_frontend_queue=from_frontend_q, # For client input
        to_backend_queue=to_backend_q # For client input to backend
    )
    queue_forwarder_task = asyncio.create_task(queue_forwarder.forward())
    logger.info("QueueForwarder task started.")

    logger.info("Application startup complete. All core services initialized.")


# --- FASTAPI APPLICATION SHUTDOWN EVENT ---
@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Application shutdown event triggered.")

    # 1. Stop the simulation if it's running
    if sim_manager_instance is not None and sim_manager_instance.running:
        await sim_manager_instance.stop()
        logger.info("SimulationManager stopped.")

    # 2. Cancel background tasks gracefully
    if message_processor_task and not message_processor_task.done():
        message_processor_task.cancel()
        try:
            await message_processor_task # Await task to complete cancellation
        except asyncio.CancelledError:
            logger.info("MessageProcessor task cancelled.")
    
    if queue_forwarder_task and not queue_forwarder_task.done():
        queue_forwarder_task.cancel()
        try:
            await queue_forwarder_task # Await task to complete cancellation
        except asyncio.CancelledError:
            logger.info("QueueForwarder task cancelled.")


    logger.info("Application shutdown complete.")


# --- DEPENDENCY INJECTION FUNCTIONS ---
# This function provides the initialized SimulationManager instance to FastAPI endpoints
def get_simulation_manager() -> SimulationManager:
    if sim_manager_instance is None:
        logger.error("SimulationManager was not initialized during startup!")
        # This error should ideally not happen if startup completes successfully
        raise RuntimeError("SimulationManager not initialized. Server startup likely failed or is incomplete.")
    return sim_manager_instance


# --- FASTAPI MIDDLEWARE ---
# CORS configuration for your application
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:9000", "http://127.0.0.1:9000"], # Your frontend URL
    allow_credentials=True,
    allow_methods=["*"], # Allow all HTTP methods
    allow_headers=["*"], # Allow all headers
)


# --- INCLUDE API ROUTERS ---
# This line integrates all the routes defined in your endpoints.py file
app.include_router(endpoints.router)
