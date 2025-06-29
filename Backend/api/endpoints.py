# Backend/api/endpoints.py

from fastapi import APIRouter, WebSocket, BackgroundTasks, Depends, HTTPException
from fastapi.websockets import WebSocketDisconnect, WebSocketState
import logging
import json
from typing import Optional, Any

from pydantic import BaseModel 

# UniversalMessage is the standard. WebSocketMessage import removed.
from ..models.UniversalMessage import UniversalMessage # Assuming DeadLetterMessage might be handled by services, not directly here unless for typing
from ..core.Queues import queues
from ..core.simulator import SimulationManager # Assuming this is the correct path
from ..dependencies import get_simulation_manager, get_websocket_manager_instance

logger = logging.getLogger(__name__)
router = APIRouter()

# The `forward_messages_to_websocket` function has been removed as its functionality
# is now handled by WebSocketManager._outgoing_messages_loop for each client.

@router.get("/")
async def root():
    return {"message": "Welcome to the Context Translator API"}

@router.get("/health")
async def health_check():
    return {"status": "healthy", "version": "0.1"}

@router.get("/metrics")
async def get_metrics():
    ws_manager_instance = get_websocket_manager_instance()
    # WebSocketManager stores connections in `self.connections` dictionary
    if ws_manager_instance is not None:
        active_connections_count = len(ws_manager_instance.connections)
        metrics = {
            "active_connections": active_connections_count
        }
        return metrics

async def start_simulation_helper(
    client_id: str,
    background_tasks: Optional[BackgroundTasks],
    manager: SimulationManager
):
    """Internal function to start simulation."""
    if not manager.is_ready:
        logger.error("SimulationManager not ready")
        # It's good practice to return an HTTPException for API errors
        raise HTTPException(status_code=503, detail="Simulation service not ready")

    if manager.is_running:
        logger.warning(f"Simulation already running, request for client: {client_id}")
        # Depending on desired behavior, this could be an error or just an info response
        # Returning a 200 with status for idempotency might be okay, or a 409 Conflict
        return {
            "status": "already_running",
            "message": "Simulation already running"
        }

    try:
        logger.info(f"Initiating simulation start for client: {client_id}")
        response = await manager.start(client_id=client_id, background_tasks=background_tasks)
        logger.info(f"Simulation started successfully: {response}")
        return response
    except Exception as e:
        logger.error(f"Failed to start simulation for client {client_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to start simulation: {str(e)}")

async def stop_simulation_helper(
    manager: SimulationManager,
    client_id: Optional[str] = None
):
    """Internal function to stop simulation."""
    logger.info(f"Received stop simulation command for client: {client_id}")
    try:
        response = await manager.stop(client_id=client_id)
        return response
    except Exception as e:
        logger.error(f"Failed to stop simulation for client {client_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to stop simulation: {str(e)}")

# Define a request model for POST /simulation/start for clarity and validation
class SimulationStartRequest(BaseModel):
    client_id: str

@router.post("/simulation/start")
async def start_simulation_endpoint(
    request_data: SimulationStartRequest, # Changed to use Pydantic model for request body
    background_tasks: BackgroundTasks,
    manager: SimulationManager = Depends(get_simulation_manager)
):
    """Endpoint to start the simulation via API call."""
    return await start_simulation_helper(
        client_id=request_data.client_id,
        background_tasks=background_tasks,
        manager=manager
    )

@router.get("/simulation/status")
async def simulation_status(
    manager: SimulationManager = Depends(get_simulation_manager)
):
    try:
        return await manager.status()
    except Exception as e:
        logger.error(f"Failed to get simulation status: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get simulation status: {str(e)}")


@router.get("/queues/debug")
async def debug_queues():
    """Debug endpoint to show detailed queue contents for all relevant queues."""
    def format_queue_item_details(item: Any) -> dict:
        item_dict: dict = {}
        if isinstance(item, UniversalMessage): # Explicitly check for UniversalMessage
            item_dict = item.model_dump(mode='json')
        elif isinstance(item, BaseModel): # Fallback for other Pydantic models
            item_dict = item.model_dump(mode='json')
        elif isinstance(item, dict):
            item_dict = item
        else:
            logger.warning(f"Debug queue item is not a dict or BaseModel: {type(item)}")
            return {"type": "unknown_item_type", "raw_content": str(item)}

        details = {
            "id": item_dict.get('id'),
            "type": item_dict.get('type', 'unknown_type'),
            "timestamp": item_dict.get('timestamp'),
            "client_id": item_dict.get('client_id'),
            "origin": item_dict.get('origin'),
            "destination": item_dict.get('destination'),
            "processing_path_count": len(item_dict.get('processing_path', [])),
            "forwarding_path_count": len(item_dict.get('forwarding_path', [])),
            "size_bytes": len(json.dumps(item_dict)) # Approximate size
        }
        
        payload = item_dict.get('payload')
        if isinstance(payload, dict):
            payload_summary = {k: (type(v).__name__ if not isinstance(v, (str, int, float, bool, list, dict)) else v) 
                               for k, v in payload.items()}
            details["payload_summary"] = str(payload_summary)[:250] + ('...' if len(str(payload_summary)) > 250 else '')
        elif payload is not None:
            details["payload_summary"] = str(payload)[:250] + ('...' if len(str(payload)) > 250 else '')

        # Specific fields for DeadLetterMessage if type matches
        if item_dict.get('type') == "system.dead_letter" and isinstance(payload, dict):
            details["dlq_reason"] = payload.get('reason')
            details["dlq_error_summary"] = str(payload.get('error_details'))[:200] + ('...' if len(str(payload.get('error_details'))) > 200 else '')
            # Optionally show original message type if available in DLQ payload
            original_message_data = payload.get('original_message_data', {})
            if isinstance(original_message_data, dict): # Ensure it's a dict before trying to get 'type'
                 details["dlq_original_message_type"] = original_message_data.get('type')


        return details

    queue_debug_info = {}
    # Ensure queues are initialized before accessing
    queues_to_debug = {
        "incoming": queues.incoming,
        "outgoing": queues.outgoing, # General outgoing queue, might be used by MessageRouter
        "websocket_out": queues.websocket_out, # Specifically for WebSocketManager to send
    }

    for name, queue_instance in queues_to_debug.items():
        if queue_instance is None:
            queue_debug_info[name] = {"status": "Not initialized"}
            continue
        try:
            # Assuming get_items_snapshot() exists and is safe to call
            items_snapshot = list(queue_instance.get_items_snapshot()) if hasattr(queue_instance, 'get_items_snapshot') else "Snapshot not available"
            queue_debug_info[name] = {
                "size": queue_instance.qsize(),
                "items_snapshot_count": len(items_snapshot) if isinstance(items_snapshot, list) else 0,
                "items_preview": [format_queue_item_details(item) for item in (items_snapshot[:5] if isinstance(items_snapshot, list) else [])] # Preview first 5
            }
        except Exception as e:
            logger.error(f"Error accessing queue '{name}' for debug: {e}", exc_info=True)
            queue_debug_info[name] = {"status": "Error accessing queue", "error": str(e)}
            
    return queue_debug_info

@router.websocket("/ws/{client_id}")
async def websocket_endpoint(websocket: WebSocket, client_id: str):
    ws_manager_instance = None
    try:
        ws_manager_instance = get_websocket_manager_instance()
    except RuntimeError as e: # Assuming get_websocket_manager_instance might raise this if not configured
        logger.error(f"WebSocketManager not initialized or accessible for client {client_id}: {e}")
        # Ensure websocket is accepted before trying to close with a reason,
        # or just let it fail if accept hasn't happened.
        # However, if manager isn't there, can't proceed.
        # FastAPI handles closing if accept() is not called.
        return # Manager not available, can't proceed.

    try:
        if ws_manager_instance is not None:
        # WebSocketManager.handle_connection now manages the full lifecycle
        # including accepting the connection, receiver/sender tasks, and cleanup.
            await ws_manager_instance.handle_connection(websocket, client_id)

    except WebSocketDisconnect:
        # This might be caught within handle_connection, but if it propagates here:
        logger.info(f"Client {client_id} disconnected (observed in /ws endpoint). WebSocketManager handles core cleanup.")
    except Exception as e:
        # General errors during the setup or if handle_connection re-raises something critical
        logger.error(f"Unhandled exception in /ws/{client_id} endpoint for client {client_id}: {str(e)}", exc_info=True)
        # WebSocketManager's handle_connection has its own robust error handling.
        # If an error escapes that, it's likely a critical issue.
        # Attempt to close if WebSocket object is still in a valid state AND accepted.
        if websocket.application_state == WebSocketState.CONNECTED and websocket.client_state == WebSocketState.CONNECTED:
             try:
                 await websocket.close(code=1011, reason=f"Internal Server Error in endpoint: {str(e)}")
             except RuntimeError: # Websocket might be already closed by another task
                 pass
    finally:
        # WebSocketManager.handle_connection has its own finally block for cleanup of its tasks and connection state.
        # This finally block in the endpoint ensures endpoint-specific logging.
        logger.info(f"WebSocket endpoint /ws/{client_id} processing finished for client {client_id}.")