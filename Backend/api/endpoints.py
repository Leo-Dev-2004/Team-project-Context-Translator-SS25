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
    def get_queue_details(queue):
        try:
            items = []
            queue_items = list(queue._queue)
            
            for item in queue_items[:20]:
                details = {
                    "type": item.get('type', 'unknown'),
                    "timestamp": item.get('timestamp'),
                    "processing_path": item.get('processing_path', []),
                    "forwarding_path": item.get('forwarding_path', []),
                    "size_bytes": len(str(item))
                }
                
                if 'data' in item:
                    data = item['data']
                    details.update({
                        "id": data.get('id'),
                        "status": data.get('status'),
                        "progress": data.get('progress'),
                        "message": data.get('message') or data.get('content')
                    })
                
                items.append(details)
            return items
        except Exception as e:
            return [{"error": str(e)}]
    
    return {
        "to_frontend_queue": {
            "size": get_to_frontend_queue().size(),
            "items": get_queue_details(get_to_frontend_queue())
        },
        "from_frontend_queue": {
            "size": get_from_frontend_queue().size(),
            "items": get_queue_details(get_from_frontend_queue())
        },
        "to_backend_queue": {
            "size": get_to_backend_queue().size(),
            "items": get_queue_details(get_to_backend_queue())
        },
        "from_backend_queue": {
            "size": get_from_backend_queue().size(),
            "items": get_queue_details(get_from_backend_queue())
        }
    }

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.handle_connection(websocket)

async def get_simulation_manager() -> SimulationManager:
    """Dependency to get initialized SimulationManager"""
    from ..backend import SimulationManager
    if SimulationManager is None:
        raise RuntimeError("SimulationManager not initialized")
    return SimulationManager

