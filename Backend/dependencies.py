# Backend/dependencies.py
import asyncio
import logging
from typing import Optional

from Backend.core.simulator import SimulationManager
from Backend.services.websocket_manager import WebSocketManager
from Backend.core.Queues import queues
logger = logging.getLogger(__name__)
_global_sim_manager_instance: Optional[SimulationManager] = None
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
        assert queues.to_backend is not None, "to_backend queue must be initialized before creating SimulationManager"
        assert queues.from_backend is not None, "from_backend queue must be initialized before creating SimulationManager"
        assert queues.to_frontend is not None, "to_frontend queue must be initialized before creating SimulationManager"
        assert queues.from_frontend is not None, "from_frontend queue must be initialized before creating SimulationManager"
        assert queues.dead_letter is not None, "dead_letter queue must be initialized before creating SimulationManager"
        # Initialize the SimulationManager with the queues
        logger.info("Creating SimulationManager instance with provided queues")
        _global_sim_manager_instance = SimulationManager(
            to_backend_queue=queues.to_backend,  # Ensure this is correct
            # FIX: Changed from_backend_queue to use get_from_backend_queue()
            from_backend_queue=queues.from_backend, # Ensure this is correct
            to_frontend_queue=queues.to_frontend,
            from_frontend_queue=queues.from_frontend,
            # FIX: Use get_dead_letter_queue() to get an actual MessageQueue instance
            dead_letter_queue=queues.dead_letter
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