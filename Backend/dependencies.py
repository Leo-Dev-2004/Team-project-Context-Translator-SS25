# Backend/dependencies.py
import asyncio
import logging
from typing import Optional
from Backend.core.simulator import SimulationManager
from Backend.queues.shared_queue import (
    get_to_backend_queue,
    get_to_frontend_queue,
    get_from_frontend_queue
)

logger = logging.getLogger(__name__)

# This global variable will hold the SimulationManager instance
_global_sim_manager_instance: Optional[SimulationManager] = None

def set_simulation_manager_instance(manager: SimulationManager):
    """
    Sets the global SimulationManager instance.
    This function will be called by backend.py during startup.
    """
    global _global_sim_manager_instance
    _global_sim_manager_instance = manager

def get_simulation_manager(require_ready: bool = True) -> SimulationManager:
    global _global_sim_manager_instance
    
    if _global_sim_manager_instance is None:
        logger.info("Initializing SimulationManager with queues")
        _global_sim_manager_instance = SimulationManager(
            to_backend_queue=get_to_backend_queue(),
            to_frontend_queue=get_to_frontend_queue(),
            from_backend_queue=get_from_frontend_queue()  # Korrekte Queue für eingehende Nachrichten
        )
        logger.info(f"SimulationManager initialized on loop {id(asyncio.get_running_loop())}")

    if require_ready and not _global_sim_manager_instance.is_ready:
        raise RuntimeError("SimulationManager not in ready state")

    logger.debug(f"Retrieved SimulationManager instance")
    return _global_sim_manager_instance
