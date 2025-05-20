from fastapi import APIRouter, WebSocket, BackgroundTasks, Depends
import asyncio
import logging
import json
from typing import Optional
from ..core.simulator import SimulationManager
from ..backend import get_simulation_manager
from ..queues.shared_queue import (
    get_to_backend_queue,
    get_to_frontend_queue,
    get_from_backend_queue,
    get_from_frontend_queue,
    get_dead_letter_queue
)
from ..services.websocket_manager import WebSocketManager

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

@router.get("/simulation/start")
async def start_simulation(
    background_tasks: BackgroundTasks,
    manager: SimulationManager = Depends(get_simulation_manager)
):
    return await manager.start(background_tasks)

@router.get("/simulation/stop")
async def stop_simulation(
    manager: SimulationManager = Depends(get_simulation_manager)
):
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
            "items": [format_queue_item_details(item) for item in 
                     get_to_frontend_queue().get_current_items_for_debug()]
        },
        "from_frontend_queue": {
            "size": get_from_frontend_queue().size(),
            "items": [format_queue_item_details(item) for item in 
                     get_from_frontend_queue().get_current_items_for_debug()]
        },
        "to_backend_queue": {
            "size": get_to_backend_queue().size(),
            "items": [format_queue_item_details(item) for item in 
                     get_to_backend_queue().get_current_items_for_debug()]
        },
        "from_backend_queue": {
            "size": get_from_backend_queue().size(),
            "items": [format_queue_item_details(item) for item in 
                     get_from_backend_queue().get_current_items_for_debug()]
        }
    }

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.handle_connection(websocket)


