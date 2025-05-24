# Backend/api/endpoints.py
from fastapi import APIRouter, WebSocket, BackgroundTasks, Depends
import asyncio
import logging
import time
import json
from typing import Optional

from fastapi.websockets import WebSocketState

from ..core.simulator import SimulationManager
from ..queues.shared_queue import (
    get_to_backend_queue,
    get_to_frontend_queue,
    get_from_backend_queue,
    get_from_frontend_queue,
    get_dead_letter_queue
)
from ..services.websocket_manager import WebSocketManager

# IMPORT THE GETTER FROM YOUR DEPENDENCIES.PY FILE
from ..dependencies import get_simulation_manager

logger = logging.getLogger(__name__)
router = APIRouter()
ws_manager = WebSocketManager()


@router.get("/")
async def root():
    return {"message": "Welcome to the Context Translator API"}

@router.get("/health")
async def health_check():
    return {"status": "healthy", "version": "0.1"}

@router.get("/metrics")
async def get_metrics():
    return ws_manager.get_metrics()

@router.post("/simulation/start")
async def start_simulation(
    background_tasks: BackgroundTasks,
    manager: SimulationManager = Depends(get_simulation_manager)
):
    logger.info("Backend: Starting simulation via API")
    try:
        response = await manager.start(background_tasks)
        logger.info(f"Simulation started successfully: {response}")
        return response
    except Exception as e:
        logger.error(f"Failed to start simulation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/simulation/stop") # Changed to POST
async def stop_simulation(
    manager: SimulationManager = Depends(get_simulation_manager)
):
    logger.info("Backend: Received POST request to /simulation/stop")
    return await manager.stop()

@router.get("/simulation/status")
async def simulation_status(
    manager: SimulationManager = Depends(get_simulation_manager)
):
    return await manager.status()

@router.get("/queues/debug")
async def debug_queues():
    """Debug endpoint to show detailed queue contents"""
    def format_queue_item_details(item: dict) -> dict:
        """Helper to format individual queue item details for consistent output."""
        details = {
            "type": item.get('type', 'unknown'),
            "timestamp": item.get('timestamp'),
            "processing_path": item.get('processing_path', []),
            "forwarding_path": item.get('forwarding_path', []),
            "size_bytes": len(json.dumps(item))
        }
        if 'data' in item:
            data = item['data']
            details.update({
                "id": data.get('id'),
                "status": data.get('status'),
                "progress": data.get('progress'),
                "message": data.get('message') or data.get('content')
            })
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
    await websocket.accept()
    logger.info(f"WebSocket connection established from {websocket.client}")

    # Register connection with WebSocketManager IMMEDIATELY after accept
    # This function should NOT close the websocket or block the main loop.
    await ws_manager.handle_connection(websocket)

    # The main connection loop. This 'try' block wraps the entire
    # active lifetime of the WebSocket connection.
    try:
        while True: # This loop keeps the connection alive
            try:
                # Attempt to receive a message with a timeout.
                # If nothing is received within 30 seconds, it will raise asyncio.TimeoutError
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=30.0 # Timeout for receiving messages
                )

                # If a message is received, handle it using the WebSocketManager
                await ws_manager.handle_message(websocket, data)

            except asyncio.TimeoutError:
                # If timeout occurs, send a ping to keep the connection alive (heartbeat)
                try:
                    await websocket.send_json({"type": "ping", "timestamp": time.time()})
                    logger.debug("Sent WebSocket ping to client.")
                except RuntimeError as e:
                    # If sending ping fails, it means the client has likely disconnected
                    logger.warning(f"Failed to send ping, client likely disconnected: {e}")
                    break # Exit the while True loop, which leads to the finally block
            except Exception as e:
                # Catch any other specific errors during message reception (e.g., client closed abruptly)
                logger.error(f"WebSocket receive error for {websocket.client}: {e}")
                break # Exit the while True loop on other errors

    # This 'except' block catches any exceptions that occur during the entire
    # lifecycle of the websocket (outside of the inner receive loop errors)
    except Exception as e:
        logger.error(f"WebSocket connection lifetime error for {websocket.client}: {e}")
    finally:
        # This 'finally' block is executed ONLY when the 'try' block (and its 'while True' loop)
        # has finished executing, either by a 'break', a 'return', or an unhandled exception.
        try:
            # Check if the websocket is still connected before trying to close it
            if websocket.client_state != WebSocketState.DISCONNECTED:
                # Close the websocket if it's not already disconnected
                await websocket.close(code=1000) # 1000 is a normal closure code
                logger.info(f"WebSocket connection explicitly closed for {websocket.client}")

            # Perform cleanup with the WebSocketManager
            await ws_manager._cleanup_connection(websocket, str(websocket.client))

        except Exception as e:
            logger.error(f"Error during WebSocket cleanup for {websocket.client}: {e}")
