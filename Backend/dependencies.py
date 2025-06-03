# Backend/dependencies.py
import asyncio
import logging
from typing import Optional

from Backend.core.simulator import SimulationManager
from Backend.services.WebSocketManager import WebSocketManager
from Backend.MessageRouter import MessageRouter # <-- NEW: Import MessageRouter
from Backend.core.Queues import queues as global_queues # <-- Renamed import for clarity

logger = logging.getLogger(__name__)

# Global instances (initially None, but set during application startup)
_global_sim_manager_instance: Optional[SimulationManager] = None
_global_ws_manager_instance: Optional[WebSocketManager] = None
_global_message_router_instance: Optional[MessageRouter] = None # <-- NEW: Global instance for MessageRouter

# --- SimulationManager Related Functions ---

def set_simulation_manager_instance(manager: SimulationManager):
    """
    Sets the global SimulationManager instance.
    This function will be called by backend.py during startup.
    """
    global _global_sim_manager_instance
    _global_sim_manager_instance = manager
    logger.debug("SimulationManager instance set in dependencies.")

def get_simulation_manager() -> SimulationManager:
    """
    Retrieves the global SimulationManager instance.
    This function assumes the instance has been set during application startup.
    """
    global _global_sim_manager_instance
    if _global_sim_manager_instance is None:
        # This RuntimeError ensures that the manager is initialized before being retrieved
        raise RuntimeError("SimulationManager not initialized. Call set_simulation_manager_instance during startup.")
    # No need for require_ready check here; that's a concern for the caller or the manager itself
    logger.debug("Retrieved SimulationManager instance.")
    return _global_sim_manager_instance

# --- WebSocketManager Related Functions ---

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
    This function assumes the instance has been set during application startup.
    """
    global _global_ws_manager_instance
    if _global_ws_manager_instance is None:
        raise RuntimeError("WebSocketManager not initialized. Call set_websocket_manager_instance during startup.")
    return _global_ws_manager_instance

# --- MessageRouter Related Functions ---

def set_message_router_instance(router: MessageRouter):
    """
    Sets the global MessageRouter instance.
    This function will be called by backend.py during startup.
    """
    global _global_message_router_instance
    _global_message_router_instance = router
    logger.debug("MessageRouter instance set in dependencies.")

def get_message_router_instance() -> MessageRouter:
    """
    Retrieves the global MessageRouter instance.
    This function assumes the instance has been set during application startup.
    """
    global _global_message_router_instance
    if _global_message_router_instance is None:
        raise RuntimeError("MessageRouter not initialized. Call set_message_router_instance during startup.")
    return _global_message_router_instance


# --- Application Startup Initialization Function ---
# This function centralizes the creation and initial setup of core components.
async def initialize_core_components():
    """
    Initializes all core backend components and sets their global instances.
    This function should be called once at application startup.
    """
    logger.info("Initializing core backend components...")

    # Queues are automatically initialized when 'global_queues' is imported.
    # We no longer need explicit asserts here, as Queues.__init__ handles it.
    logger.info("Global queues are ready via Backend.core.Queues.queues import.")

    # 1. Initialize MessageRouter
    # The MessageRouter takes no constructor arguments as it accesses global_queues directly
    router = MessageRouter()
    set_message_router_instance(router)
    await router.start() # Start the router's listening loop
    logger.info("MessageRouter initialized and started.")

    # 2. Initialize SimulationManager
    # SimulationManager now directly accesses global_queues, no need to pass them
    sim_manager = SimulationManager()
    set_simulation_manager_instance(sim_manager)
    # The sim_manager.is_ready check is now the responsibility of the SimulationManager itself
    logger.info("SimulationManager initialized.")

    # 3. Initialize WebSocketManager
    # WebSocketManager also accesses global_queues directly
    ws_manager = WebSocketManager()
    set_websocket_manager_instance(ws_manager)
    await ws_manager.start() # Start the WebSocketManager's listening loop
    logger.info("WebSocketManager initialized and started.")

    logger.info("All core backend components initialized and started.")

# --- Application Shutdown Function ---
async def shutdown_core_components():
    """
    Performs graceful shutdown of all core backend components.
    This function should be called once at application shutdown.
    """
    logger.info("Shutting down core backend components...")

    # Stop components in reverse order of dependency/startup
    if _global_ws_manager_instance:
        await _global_ws_manager_instance.stop()
        logger.info("WebSocketManager stopped.")

    # The SimulationManager might not have a dedicated 'stop' method if its tasks are short-lived.
    # If it has long-running tasks, add `await _global_sim_manager_instance.stop()` here.
    # For now, we'll assume it doesn't need an explicit stop beyond its tasks finishing.
    if _global_sim_manager_instance:
        # If SimulationManager has async tasks that need stopping, implement a .stop() method.
        # For example: await _global_sim_manager_instance.stop()
        logger.info("SimulationManager shutdown procedures completed (if any).")


    if _global_message_router_instance:
        await _global_message_router_instance.stop()
        logger.info("MessageRouter stopped.")

    # Drain queues during shutdown to ensure no messages are lost
    await global_queues.incoming.drain()
    await global_queues.outgoing.drain()
    await global_queues.websocket_out.drain()
    # It's usually good to keep dead_letter for later inspection, so no drain for it.
    logger.info("All primary queues drained during shutdown.")

    logger.info("Core backend components shut down gracefully.")