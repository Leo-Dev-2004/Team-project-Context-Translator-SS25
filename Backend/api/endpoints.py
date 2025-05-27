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
from ..services.websocket_manager import WebSocketManager
from ..models.message_types import WebSocketMessage

# IMPORT THE GETTER FROM YOUR DEPENDENCIES.PY FILE
from ..dependencies import get_simulation_manager

logger = logging.getLogger(__name__)
router = APIRouter()
ws_manager = WebSocketManager()

# --- FIX: Move forward_messages_to_websocket definition here, BEFORE websocket_endpoint ---
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
                    
                    await websocket.send_text(json.dumps(message_to_send))
                    logger.debug(f"Forwarded message from queue to client: {message_to_send.get('type')}")
                except Exception as e:
                    logger.error(f"Failed to send message from queue to websocket ({websocket.client}): {e}", exc_info=True)
                    break
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
    return ws_manager.get_metrics()

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
    # This call relies on manager.stop being updated in Backend/core/simulator.py
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
            "size": get_to_frontend_queue().size(),
            "items": [format_queue_item_details(item) for item in get_to_frontend_queue().get_current_items_for_debug()]
        },
        "from_frontend_queue": {
            "size": get_from_frontend_queue().size(),
            "items": [format_queue_item_details(item) for item in get_from_frontend_queue().get_current_items_for_debug()]
        },
        "to_backend_queue": {
            "size": get_to_backend_queue().size(),
            "items": [format_queue_item_details(item) for item in get_to_backend_queue().get_current_items_for_debug()]
        },
        "from_backend_queue": {
            "size": get_from_backend_queue().size(),
            "items": [format_queue_item_details(item) for item in get_from_backend_queue().get_current_items_for_debug()]
        }
    }

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Handle WebSocket connections with proper error handling and cleanup."""
    forwarder_task = None
    try:
        await websocket.accept()
        # --- FIX: forward_messages_to_websocket is now defined above ---
        forwarder_task = asyncio.create_task(
            forward_messages_to_websocket(websocket, get_to_frontend_queue())
        )
        logger.info(f"WebSocket connection established from {websocket.client}")

        await ws_manager.handle_connection(websocket)

        manager = get_simulation_manager(require_ready=False)

        while True:
            try:
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=30.0
                )

                try:
                    message_from_client = json.loads(data)
                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON received from {websocket.client}: {data}")
                    await ws_manager._send_error(websocket, f"Invalid JSON format: {data[:50]}...")
                    continue

                if message_from_client.get('type') == 'ping':
                    await websocket.send_text(json.dumps({"type": "pong", "timestamp": time.time()}))
                    logger.debug(f"Responded with pong to {websocket.client}.")
                    continue

                try:
                    ws_message = WebSocketMessage.parse_obj(message_from_client)
                    ws_message.client_id = ws_message.client_id or str(websocket.client)
                except Exception as e:
                    logger.error(f"Validation error for incoming WebSocket message: {e}", exc_info=True)
                    await ws_manager._send_error(websocket, f"Invalid message structure: {str(e)}")
                    continue


                if ws_message.type == 'command':
                    command = ws_message.data.get('command')
                    if command == 'start_simulation':
                        logger.info(f"Received start_simulation command via WebSocket from {ws_message.client_id}")
                        await start_simulation_helper(
                            client_id=ws_message.client_id,
                            background_tasks=None,
                            manager=manager
                        )
                    elif command == 'stop_simulation':
                        logger.info(f"Received stop_simulation command via WebSocket from {ws_message.client_id}")
                        await stop_simulation_helper(
                            manager=manager,
                            client_id=ws_message.client_id
                        )
                    else:
                        logger.warning(f"Unknown command received: {command} from {ws_message.client_id}")
                        await ws_manager._send_error(websocket, f"Unknown command: {command}")
                else:
                    await ws_manager.handle_message(websocket, data)

            except asyncio.TimeoutError:
                logger.debug(f"No message from {websocket.client} for 30s (client inactivity timeout).")
                continue

            except Exception as e:
                logger.error(f"WebSocket receive/process error for {websocket.client}: {e}", exc_info=True)
                break

    except WebSocketDisconnect:
        logger.info(f"Client {websocket.client} disconnected normally from /ws endpoint")
    except Exception as e:
        logger.error(f"Unexpected WebSocket error for {websocket.client} in /ws endpoint: {str(e)}", exc_info=True)
    finally:
        if forwarder_task and not forwarder_task.done():
            forwarder_task.cancel()
            try:
                await forwarder_task
            except asyncio.CancelledError:
                pass
        logger.info(f"Cleanup finished for {websocket.client} at /ws endpoint's finally block. WebSocketManager handles core connection cleanup.")