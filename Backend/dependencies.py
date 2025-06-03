# Backend/dependencies.py
import asyncio
import logging
from typing import Optional, cast # Keep cast for now if you need it elsewhere, but it won't be for queues.

# Import the abstract queue type correctly
from Backend.queues.QueueTypes import AbstractMessageQueue # Corrected import

from Backend.core.SimulationManager import SimulationManager
from Backend.services.WebSocketManager import WebSocketManager # Assuming Backend.services is the correct path for WebSocketManager
from Backend.MessageRouter import MessageRouter
from Backend.core.Queues import queues

logger = logging.getLogger(__name__)

# Global instances (initially None, but set during application startup)
_global_sim_manager_instance: Optional[SimulationManager] = None
_global_ws_manager_instance: Optional[WebSocketManager] = None
_global_message_router_instance: Optional[MessageRouter] = None

# --- SimulationManager Related Functions ---

def set_simulation_manager_instance(manager: SimulationManager):
    global _global_sim_manager_instance
    _global_sim_manager_instance = manager
    logger.debug("SimulationManager instance set in dependencies.")

def get_simulation_manager() -> SimulationManager:
    global _global_sim_manager_instance
    if _global_sim_manager_instance is None:
        raise RuntimeError("SimulationManager not initialized. Call set_simulation_manager_instance during startup.")
    logger.debug("Retrieved SimulationManager instance.")
    return _global_sim_manager_instance

# --- WebSocketManager Related Functions ---

def set_websocket_manager_instance(manager: WebSocketManager):
    global _global_ws_manager_instance
    _global_ws_manager_instance = manager
    logger.debug("WebSocketManager instance set in dependencies.")

def get_websocket_manager_instance() -> WebSocketManager:
    global _global_ws_manager_instance
    if _global_ws_manager_instance is None:
        raise RuntimeError("WebSocketManager not initialized. Call set_websocket_manager_instance during startup.")
    return _global_ws_manager_instance

# --- MessageRouter Related Functions ---

def set_message_router_instance(router: MessageRouter):
    global _global_message_router_instance
    _global_message_router_instance = router
    logger.debug("MessageRouter instance set in dependencies.")

def get_message_router_instance() -> MessageRouter:
    global _global_message_router_instance
    if _global_message_router_instance is None:
        raise RuntimeError("MessageRouter not initialized. Call set_message_router_instance during startup.")
    return _global_message_router_instance


# --- Application Startup Initialization Function ---
async def initialize_core_components():
    logger.info("Initializing core backend components...")

    logger.info("Global queues are ready via Backend.core.Queues.queues import.")

    # 1. Initialize MessageRouter
    # The MessageRouter takes no constructor arguments as it accesses global_queues directly
    router = MessageRouter()
    set_message_router_instance(router)
    await router.start()
    logger.info("MessageRouter initialized and started.")

    # 2. Initialize SimulationManager
    # Pass the required queues to SimulationManager, using AbstractMessageQueue type
    sim_manager = SimulationManager(
        incoming_queue=queues.incoming, # No cast needed if type hints are consistent
        outgoing_queue=queues.outgoing,
        websocket_out_queue=queues.websocket_out,
        dead_letter_queue=queues.dead_letter
    )
    set_simulation_manager_instance(sim_manager)
    logger.info("SimulationManager initialized.")

    # 3. Initialize WebSocketManager
    # WebSocketManager also accesses global_queues directly, using AbstractMessageQueue type
    ws_manager = WebSocketManager(
        incoming_queue=queues.incoming, # No cast needed if type hints are consistent
        websocket_out_queue=queues.websocket_out,
        dead_letter_queue=queues.dead_letter
    )
    set_websocket_manager_instance(ws_manager)
    await ws_manager.start()
    logger.info("WebSocketManager initialized and started.")

    logger.info("All core backend components initialized and started.")

# --- Application Shutdown Function ---
async def shutdown_core_components():
    logger.info("Shutting down core backend components...")

    if _global_ws_manager_instance:
        await _global_ws_manager_instance.stop()
        logger.info("WebSocketManager stopped.")

    if _global_sim_manager_instance:
        # Assuming SimulationManager has a stop method if it runs async tasks
        # If not, remove this line or add a pass
        # await _global_sim_manager_instance.stop()
        logger.info("SimulationManager shutdown procedures completed (if any).")

    if _global_message_router_instance:
        await _global_message_router_instance.stop()
        logger.info("MessageRouter stopped.")

    await queues.incoming.drain()
    await queues.outgoing.drain()
    await queues.websocket_out.drain()
    logger.info("All primary queues drained during shutdown.")

    logger.info("Core backend components shut down gracefully.")