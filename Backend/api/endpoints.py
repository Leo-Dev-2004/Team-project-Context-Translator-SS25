# Backend/api/endpoints.py

from fastapi import APIRouter, WebSocket
from fastapi.websockets import WebSocketDisconnect, WebSocketState
import logging
import json
from typing import Any

from pydantic import BaseModel

from ..models.UniversalMessage import UniversalMessage
from ..core.Queues import queues
from ..dependencies import get_websocket_manager_instance

logger = logging.getLogger(__name__)
router = APIRouter()

# --- Standard- und Debug-Endpunkte ---

@router.get("/")
async def root():
    """Root-Endpunkt, der eine Willkommensnachricht zurückgibt."""
    return {"message": "Welcome to the Context Translator API"}

@router.get("/health")
async def health_check():
    """Health-Check-Endpunkt zur Überwachung des Service-Status."""
    return {"status": "healthy", "version": "0.1"}

@router.get("/metrics")
async def get_metrics():
    """Gibt grundlegende Metriken zurück, wie z.B. die Anzahl aktiver WebSocket-Verbindungen."""
    ws_manager_instance = get_websocket_manager_instance()
    if ws_manager_instance:
        active_connections_count = len(ws_manager_instance.connections)
        return {"active_connections": active_connections_count}
    return {"active_connections": 0}

@router.get("/queues/debug")
async def debug_queues():
    """Debug-Endpunkt, um den Inhalt und Zustand der Queues zur Laufzeit zu inspizieren."""
    def format_queue_item_details(item: Any) -> dict:
        item_dict = {}
        if isinstance(item, UniversalMessage):
            item_dict = item.model_dump(mode='json')
        elif isinstance(item, BaseModel):
            item_dict = item.model_dump(mode='json')
        else:
            return {"type": "unknown_item_type", "raw_content": str(item)}

        details = {
            "id": item_dict.get('id'),
            "type": item_dict.get('type'),
            "client_id": item_dict.get('client_id'),
            "origin": item_dict.get('origin'),
        }
        return details

    queue_debug_info = {}
    queues_to_debug = {
        "incoming": queues.incoming,
        "outgoing": queues.outgoing,
        "websocket_out": queues.websocket_out,
    }

    for name, q in queues_to_debug.items():
        if q is None:
            queue_debug_info[name] = {"status": "Not initialized"}
            continue
        
        items_snapshot = list(q.get_items_snapshot()) if hasattr(q, 'get_items_snapshot') else "Snapshot not available"
        queue_debug_info[name] = {
            "size": q.qsize(),
            "items_preview": [format_queue_item_details(item) for item in (items_snapshot[:5] if isinstance(items_snapshot, list) else [])]
        }
            
    return queue_debug_info

# --- WebSocket-Endpunkt ---
@router.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    """
    Der zentrale WebSocket-Endpunkt. Er delegiert die gesamte Logik
    der Verbindungsverwaltung an den WebSocketManager.
    """
    ws_manager = get_websocket_manager_instance()
    if not ws_manager:
        logger.error("WebSocketManager not initialized when a connection was attempted. Closing connection.")
        await websocket.close(code=1011, reason="Server internal error: WebSocketManager not ready.")
        return

    try:
        await ws_manager.handle_connection(websocket, client_id)
    except WebSocketDisconnect:
        logger.info(f"Client {client_id} disconnected (observed in /ws endpoint).")
    except Exception as e:
        logger.error(f"Unhandled exception in /ws/{client_id} endpoint: {e}", exc_info=True)
        if websocket.application_state != WebSocketState.DISCONNECTED:
             await websocket.close(code=1011, reason=f"Internal Server Error")
    finally:
        logger.info(f"WebSocket endpoint processing finished for client {client_id}.")