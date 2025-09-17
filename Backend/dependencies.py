# In Backend/dependencies.py (Refined for consistency)

from typing import Optional
from .services.WebSocketManager import WebSocketManager
from .core.simulator import SimulationManager
from .core.session_manager import SessionManager
from .shared.communications.ConnectionManager import ConnectionManager

# --- Module-level variables with a consistent '_' prefix ---
_session_manager_instance: Optional[SessionManager] = None
_websocket_manager_instance: Optional[WebSocketManager] = None
_simulation_manager_instance: Optional[SimulationManager] = None
_connection_manager_instance: Optional[ConnectionManager] = None

# --- Session Manager ---
def set_session_manager_instance(instance: SessionManager):
    global _session_manager_instance
    _session_manager_instance = instance
def get_session_manager_instance() -> Optional[SessionManager]:
    return _session_manager_instance

# --- WebSocket Manager ---
def set_websocket_manager_instance(instance: WebSocketManager):
    global _websocket_manager_instance
    _websocket_manager_instance = instance
def get_websocket_manager_instance() -> Optional[WebSocketManager]:
    return _websocket_manager_instance

# --- Simulation Manager ---
def set_simulation_manager_instance(instance: SimulationManager):
    global _simulation_manager_instance
    _simulation_manager_instance = instance
def get_simulation_manager_instance() -> Optional[SimulationManager]: # Renamed for consistency
    return _simulation_manager_instance

# --- Connection Manager ---
def set_connection_manager_instance(instance: ConnectionManager):
    global _connection_manager_instance
    _connection_manager_instance = instance
def get_connection_manager_instance() -> Optional[ConnectionManager]:
    return _connection_manager_instance