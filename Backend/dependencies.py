# Backend/dependencies.py
from typing import Optional
from .services.WebSocketManager import WebSocketManager
from .core.session_manager import SessionManager

_global_session_manager_instance: Optional[SessionManager] = None

def set_session_manager_instance(instance: SessionManager):
    global _global_session_manager_instance
    _global_session_manager_instance = instance

def get_session_manager_instance() -> Optional[SessionManager]:
    return _global_session_manager_instance

# Global instance for WebSocketManager
_global_ws_manager_instance: Optional[WebSocketManager] = None

def set_websocket_manager_instance(instance: WebSocketManager):
    global _global_ws_manager_instance
    _global_ws_manager_instance = instance

def get_websocket_manager_instance() -> Optional[WebSocketManager]:
    return _global_ws_manager_instance