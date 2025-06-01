# Backend/api/endpoints.py

from fastapi import APIRouter, WebSocket, BackgroundTasks, Depends, HTTPException
import asyncio
from fastapi.websockets import WebSocketDisconnect, WebSocketState
import logging
import time
import json
from typing import Optional, Any # Ensure Any is imported

# Ensure BaseModel is imported for type checking
from pydantic import BaseModel

# Ensure these imports are correct based on your file structure
from ..core.simulator import SimulationManager
from ..queues.shared_queue import (
    get_to_backend_queue,
    get_to_frontend_queue,
    get_from_backend_queue,
    get_from_frontend_queue,
    get_dead_letter_queue
)
# REMOVED: direct import and instantiation of WebSocketManager here
# from ..services.websocket_manager import WebSocketManager # No longer directly instantiated here
from ..models.message_types import WebSocketMessage

# IMPORT THE GETTER FOR SIMULATION MANAGER AND THE NEW GETTER FOR WEBSOCKET MANAGER
from ..dependencies import get_simulation_manager, get_websocket_manager_instance # ADDED get_websocket_manager_instance

logger = logging.getLogger(__name__)
router = APIRouter()

# REMOVED: This line is problematic because it creates a *new* instance
# ws_manager = WebSocketManager() # This creates a *separate* instance, not the global one.

# --- FIX: Move forward_messages_to_websocket definition here, BEFORE websocket_endpoint ---
# This function is now **redundant** if QueueForwarder fully handles to_frontend_queue.
# If you still want to run it *in addition* to QueueForwarder (e.g., for direct client-specific forwarding tasks),
# ensure its logic doesn't conflict with QueueForwarder.
# For now, I'm keeping it as you provided, but be aware of potential redundancies.
async def forward_messages_to_websocket(websocket: WebSocket, queue):
    """Continuously forward messages from queue to websocket."""
    try:
        while True:
            message = await queue.dequeue()
            if message:
                try:
                    if isinstance(message, WebSocketMessage):
                        message_to_send = message.model_dump(mode='json')
                    elif isinstance(message, dict):
                        message_to_send = message
                    else:
                        logger.error(f"Cannot serialize message of type {type(message)} from queue for WebSocket: {message}")
                        continue

                    # Direct send from this endpoint's task
                    await websocket.send_text(json.dumps(message_to_send))
                    logger.debug(f"Forwarded message from queue to client: {message_to_send.get('type')}")
                except Exception as e:
                    logger.error(f"Failed to send message from queue to websocket ({websocket.client}): {e}", exc_info=True)
                    # Break the loop if sending to this specific websocket fails
                    break
            # Small sleep to prevent busy-waiting when queue is empty
            await asyncio.sleep(0.01)
    except asyncio.CancelledError:
        logger.info(f"Message forwarding task for {websocket.client} cancelled.")
    except Exception as e:
        logger.error(f"Message forwarding task for {websocket.client} failed: {e}", exc_info=True)
# --- END FIX ---


@router.get("/")
async def root():
    return {"message": "Welcome to the Context Translator API"}

@router.get("/health")
async def health_check():
    return {"status": "healthy", "version": "0.1"}

@router.get("/metrics")
async def get_metrics():
    # MODIFIED: Get the global WebSocketManager instance for metrics
    ws_manager_instance = get_websocket_manager_instance()
    # Example: Return number of active connections if such an attribute exists
    # Replace 'active_connections' with the actual attribute or method you want to expose
    metrics = {
        "active_connections": getattr(ws_manager_instance, "active_connections", "unknown")
    }
    return metrics

async def start_simulation_helper(
    client_id: str,
    background_tasks: Optional[BackgroundTasks],
    manager: SimulationManager
):
    """Internal function to start simulation, now called from WebSocket handler or API endpoint."""
    if not manager.is_ready:
        logger.error("SimulationManager not ready")
        return {
            "status": "error",
            "message": "Simulation service not ready"
        }

    if manager.is_running:
        logger.warning("Simulation already running")
        return {
            "status": "running",
            "message": "Simulation already running"
        }

    try:
        logger.info(f"Initiating simulation start for client: {client_id}")
        response = await manager.start(client_id=client_id, background_tasks=background_tasks)
        logger.info(f"Simulation started successfully: {response}")
        return response
    except Exception as e:
        logger.error(f"Failed to start simulation: {str(e)}", exc_info=True)
        return {
            "status": "error",
            "message": f"Failed to start simulation: {str(e)}"
        }

async def stop_simulation_helper(
    manager: SimulationManager,
    client_id: Optional[str] = None
):
    """Internal function to stop simulation, now called from WebSocket handler or API endpoint."""
    logger.info(f"Received stop simulation command for client: {client_id}")
    return await manager.stop(client_id=client_id)


@router.post("/simulation/start")
async def start_simulation_endpoint(
    client_id: str,
    background_tasks: BackgroundTasks,
    manager: SimulationManager = Depends(get_simulation_manager)
):
    """Endpoint to start the simulation via API call."""
    return await start_simulation_helper(
        client_id=client_id,
        background_tasks=background_tasks,
        manager=manager
    )

@router.get("/simulation/status")
async def simulation_status(
    manager: SimulationManager = Depends(get_simulation_manager)
):
    return await manager.status()

@router.get("/queues/debug")
async def debug_queues():
    """Debug endpoint to show detailed queue contents"""
    def format_queue_item_details(item: Any) -> dict:
        """Helper to format individual queue item details for consistent output."""
        if isinstance(item, BaseModel):
            item_dict = item.model_dump(mode='json')
        elif isinstance(item, dict):
            item_dict = item
        else:
            logger.warning(f"Debug queue item is not a dict or BaseModel: {type(item)}")
            return {"type": "unknown", "message": f"Non-dict/BaseModel item: {str(item)}"}

        details = {
            "type": item_dict.get('type', 'unknown'),
            "timestamp": item_dict.get('timestamp'),
            "processing_path": item_dict.get('processing_path', []),
            "forwarding_path": item_dict.get('forwarding_path', []),
            "size_bytes": len(json.dumps(item_dict))
        }
        if 'data' in item_dict:
            data = item_dict['data']
            details.update({
                "id": data.get('id'),
                "status": data.get('status'),
                "progress": data.get('progress'),
                "message": data.get('message') or data.get('content')
            })
        elif 'id' in item_dict:
            details["id"] = item_dict.get('id')
        return details


    return {
        "to_frontend_queue": {
            "size": get_to_frontend_queue().qsize(),
            "items": [format_queue_item_details(item) for item in list(get_to_frontend_queue().get_items_snapshot())]
        },
        "from_frontend_queue": {
            "size": get_from_frontend_queue().qsize(),
            "items": [format_queue_item_details(item) for item in list(get_from_frontend_queue().get_items_snapshot())]
        },
        "to_backend_queue": {
            "size": get_to_backend_queue().qsize(),
            "items": [format_queue_item_details(item) for item in list(get_to_backend_queue().get_items_snapshot())]
        },
        "from_backend_queue": {
            "size": get_from_backend_queue().qsize(),
            "items": [format_queue_item_details(item) for item in list(get_from_backend_queue().get_items_snapshot())]
        }
    }

@router.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    ws_manager_instance = None
    try:
        ws_manager_instance = get_websocket_manager_instance()
    except RuntimeError as e:
        logger.error(f"WebSocketManager not initialized in endpoint: {e}")
        await websocket.close(code=1011) # Internal Error
        return

    try:
        # ws_manager_instance.handle_connection handles the accept and receive loop
        # The while True loop for receiving messages is now handled by ws_manager_instance.handle_connection
        # So, you should NOT have another while True loop here.
        # This endpoint just sets up the connection and delegates the handling.

        # The `handle_connection` method itself contains the `while True` loop
        # for receiving messages and should enqueue them.
        # So, the `while True` loop that was here previously for receiving messages
        # should be removed from `websocket_endpoint`.

        await ws_manager_instance.handle_connection(websocket, client_id)

        # After handle_connection finishes (i.e., websocket disconnects or errors)
        # the control flow will reach here.

    except WebSocketDisconnect:
        logger.info(f"Client {client_id} disconnected normally from /ws endpoint.")
    except Exception as e:
        logger.error(f"Unexpected WebSocket error for {client_id} in /ws endpoint: {str(e)}", exc_info=True)
        if websocket.client_state == WebSocketState.CONNECTING or websocket.client_state == WebSocketState.CONNECTED:
            await websocket.close(code=1011) # Internal Error
    finally:
        logger.info(f"Cleanup finished for {client_id} at /ws endpoint's finally block. WebSocketManager handles core connection cleanup.")