# Backend/dependencies.py
from typing import Optional
from .services.WebSocketManager import WebSocketManager
from .core.session_manager import SessionManager
from .core.settings_manager import SettingsManager

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

# Global instance for SettingsManager
_global_settings_manager_instance: Optional[SettingsManager] = None

def set_settings_manager_instance(instance: SettingsManager):
    global _global_settings_manager_instance
    _global_settings_manager_instance = instance

def get_settings_manager_instance() -> Optional[SettingsManager]:
    return _global_settings_manager_instance

# Global instance for ExplanationDeliveryService
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .services.ExplanationDeliveryService import ExplanationDeliveryService

_global_explanation_delivery_service_instance: Optional['ExplanationDeliveryService'] = None

def set_explanation_delivery_service_instance(instance: 'ExplanationDeliveryService'):
    global _global_explanation_delivery_service_instance
    _global_explanation_delivery_service_instance = instance

def get_explanation_delivery_service_instance() -> Optional['ExplanationDeliveryService']:
    return _global_explanation_delivery_service_instance


