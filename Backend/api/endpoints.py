# Backend/api/endpoints.py
from fastapi import APIRouter, WebSocket, BackgroundTasks, Depends
import asyncio
import logging
import time
import json
from typing import Optional

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
from ..dependencies import get_simulation_manager # NEW IMPORT

logger = logging.getLogger(__name__)
router = APIRouter()
ws_manager = WebSocketManager() # Consider if this should also be managed as a dependency

@router.get("/")
async def root():
    return {"message": "Welcome to the Context Translator API"}

@router.get("/health")
async def health_check():
    return {"status": "healthy", "version": "0.1"}

@router.get("/metrics")
async def get_metrics():
    return ws_manager.get_metrics()

@router.get("/simulation/start")
async def start_simulation(
    background_tasks: BackgroundTasks,
    manager: SimulationManager = Depends(get_simulation_manager) # Use the imported dependency
):
    return await manager.start(background_tasks)

@router.get("/simulation/stop")
async def stop_simulation(
    manager: SimulationManager = Depends(get_simulation_manager) # Use the imported dependency
):
    return await manager.stop()

@router.get("/simulation/status")
async def simulation_status(
    manager: SimulationManager = Depends(get_simulation_manager) # Use the imported dependency
):
    return await manager.status()

@router.get("/queues/debug")
async def debug_queues():
    """Debug endpoint to show detailed queue contents"""
    # Assuming get_current_items_for_debug exists in AsyncQueue in shared_queue.py
    # If not, you need to add it or revert to inline function (less clean)
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
    try:
        await websocket.accept()
        logger.info(f"WebSocket connection established from {websocket.client}")
        
        # Add connection to active set
        app.state.websockets.add(websocket)
        
        # Enhanced heartbeat with state tracking
        last_active = time.time()
        connection_active = True
        while True:
            try:
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=30.0  # 30 second timeout for heartbeat
                )
                
                # Process message
                await ws_manager.handle_message(websocket, data)
                
                # Send periodic ping
                await websocket.send_json({"type": "ping", "timestamp": time.time()})
                
            except asyncio.TimeoutError:
                # Send ping to check connection
                await websocket.send_json({"type": "ping", "timestamp": time.time()})
                continue
                
            except Exception as e:
                logger.error(f"WebSocket error: {str(e)}")
                break
                
    except Exception as e:
        logger.error(f"WebSocket connection failed: {str(e)}")
    finally:
        await websocket.close(code=1000)
        logger.info("WebSocket connection closed cleanly")
