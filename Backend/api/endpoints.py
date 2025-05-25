# Backend/api/endpoints.py
from fastapi import APIRouter, WebSocket, BackgroundTasks, Depends, HTTPException
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

@router.get("/api/simulation/start")
async def start_simulation(
    background_tasks: BackgroundTasks,
    manager: SimulationManager = Depends(get_simulation_manager)
):
    """Start the simulation
    
    Returns:
        dict: Status message and simulation state
    Raises:
        HTTPException: If simulation fails to start
    """
    logger.info("Received request to start simulation")
    
    if not manager.is_ready:
        logger.error("SimulationManager not ready")
        raise HTTPException(
            status_code=503,
            detail="Simulation service not ready"
        )
        
    if manager.is_running:
        logger.warning("Simulation already running")
        return {
            "message": "Simulation already running",
            "status": "running",
            "timestamp": time.time()
        }
        
    try:
        logger.info("Initiating simulation start via background task")
        response = await manager.start(background_tasks)
        logger.info(f"Simulation started successfully: {response}")
        
        return {
            **response,
            "timestamp": time.time()
        }
    except HTTPException:
        raise  # Re-raise already handled HTTP exceptions
    except Exception as e:
        logger.error(f"Failed to start simulation: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start simulation: {str(e)}"
        )

@router.get("/api/simulation/stop")
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
    """Handle WebSocket connections with proper error handling and cleanup."""
    try:
        await websocket.accept()
        logger.info(f"WebSocket connection established from {websocket.client}")
        
        # Register connection with WebSocketManager IMMEDIATELY after accept
        await ws_manager.handle_connection(websocket)
        
        # Main connection loop
        while True:
            try:
                # Attempt to receive a message with a timeout
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=30.0  # Timeout for receiving messages
                )
                
                # Process received message
                await ws_manager.handle_message(websocket, data)
                
            except asyncio.TimeoutError:
                # Send ping to keep connection alive
                try:
                    await websocket.send_json({"type": "ping", "timestamp": time.time()})
                    logger.debug("Sent WebSocket ping to client.")
                except RuntimeError as e:
                    logger.warning(f"Failed to send ping, client likely disconnected: {e}")
                    break
                except Exception as e:
                    logger.error(f"Error sending ping: {e}")
                    break
                    
            except Exception as e:
                logger.error(f"WebSocket receive error: {e}")
                break

    except Exception as e:
        logger.error(f"WebSocket connection error: {e}")
    finally:
        # Cleanup connection
        try:
            if websocket.client_state != WebSocketState.DISCONNECTED:
                await websocket.close(code=1000)
                logger.info(f"Closed WebSocket connection for {websocket.client}")
                
            await ws_manager._cleanup_connection(websocket, str(websocket.client))
        except Exception as e:
            logger.error(f"Error during WebSocket cleanup: {e}")
