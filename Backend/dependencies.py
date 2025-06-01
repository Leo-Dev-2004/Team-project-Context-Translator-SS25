# Backend/dependencies.py
import asyncio
import logging
from typing import Optional
from Backend.core.simulator import SimulationManager
from Backend.queues.shared_queue import (
    get_from_backend_queue,
    get_to_backend_queue,
    get_to_frontend_queue,
    get_from_frontend_queue,
    # ADDED: Import get_dead_letter_queue
    get_dead_letter_queue
)
# ADDED: Import WebSocketManager and its getter/setter
from Backend.services.websocket_manager import WebSocketManager


logger = logging.getLogger(__name__)

# This global variable will hold the SimulationManager instance
_global_sim_manager_instance: Optional[SimulationManager] = None

# This global variable will hold the WebSocketManager instance
_global_ws_manager_instance: Optional[WebSocketManager] = None


def set_simulation_manager_instance(manager: SimulationManager):
    """
    Sets the global SimulationManager instance.
    This function will be called by backend.py during startup.
    """
    global _global_sim_manager_instance
    _global_sim_manager_instance = manager
    logger.debug("SimulationManager instance set in dependencies.")


def get_simulation_manager(require_ready: bool = True) -> SimulationManager:
    global _global_sim_manager_instance

    if _global_sim_manager_instance is None:
        logger.info("Initializing SimulationManager with queues")
        _global_sim_manager_instance = SimulationManager(
            to_backend_queue=get_to_backend_queue(),
            # FIX: Changed from_backend_queue to use get_from_backend_queue()
            from_backend_queue=get_from_backend_queue(), # Ensure this is correct
            to_frontend_queue=get_to_frontend_queue(),
            from_frontend_queue=get_from_frontend_queue(),
            # FIX: Use get_dead_letter_queue() to get an actual MessageQueue instance
            dead_letter_queue=get_dead_letter_queue()
        )
        logger.info(f"SimulationManager initialized on loop {id(asyncio.get_running_loop())}")

    if require_ready and not _global_sim_manager_instance.is_ready: # Ensure _is_ready is `is_ready`
        raise RuntimeError("SimulationManager not in ready state")

    logger.debug("Retrieved SimulationManager instance")
    return _global_sim_manager_instance


def set_websocket_manager_instance(manager: WebSocketManager):
    """
    Sets the global WebSocketManager instance.
    This function will be called by backend.py during startup.
    """
    global _global_ws_manager_instance
    _global_ws_manager_instance = manager
    logger.debug("WebSocketManager instance set in dependencies.")


def get_websocket_manager_instance() -> WebSocketManager:
    """
    Retrieves the global WebSocketManager instance.
    """
    if _global_ws_manager_instance is None:
        # This case should ideally not happen if startup initializes it correctly,
        # but provides a fallback or error for direct calls before startup.
        raise RuntimeError("WebSocketManager not initialized. Call set_websocket_manager_instance first.")
    return _global_ws_manager_instance