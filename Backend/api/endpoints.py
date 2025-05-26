# Backend/api/endpoints.py
from fastapi import APIRouter, WebSocket, BackgroundTasks, Depends, HTTPException
from fastapi.websockets import WebSocketDisconnect
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

async def start_simulation(
    background_tasks: Optional[BackgroundTasks],
    manager: SimulationManager
):
    """Internal function to start simulation, now called from WebSocket handler"""
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
        logger.info("Initiating simulation start")
        response = await manager.start(background_tasks)
        logger.info(f"Simulation started successfully: {response}")
        return response
    except Exception as e:
        logger.error(f"Failed to start simulation: {str(e)}", exc_info=True)
        return {
            "status": "error",
            "message": f"Failed to start simulation: {str(e)}"
        }

async def stop_simulation(manager: SimulationManager):
    """Internal function to stop simulation, now called from WebSocket handler"""
    logger.info("Received stop simulation command")
    return await manager.stop()

@router.post("/simulation/start")
async def start_simulation_endpoint(
    background_tasks: BackgroundTasks,
    manager: SimulationManager = Depends(get_simulation_manager)
):
    """Endpoint to start the simulation"""
    return await start_simulation(background_tasks, manager)

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
        
        # Get simulation manager instance
        manager = get_simulation_manager(require_ready=False)
        
        # Main connection loop
        while True:
            try:
                # Attempt to receive a message with a timeout
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=30.0  # Timeout for receiving messages
                )
                
                # Process received message
                if isinstance(data, str):
                    try:
                        data = json.loads(data)
                    except json.JSONDecodeError:
                        logger.error(f"Invalid JSON received: {data}")
                        continue
                
                # Handle ping/pong
                if data.get('type') == 'ping':
                    await websocket.send_json({
                        "type": "pong",
                        "timestamp": time.time()
                    })
                    continue
                    
                # Handle command messages
                if data.get('type') == 'command':
                    command = data.get('command')
                    if command == 'start_simulation':
                        logger.info("Received start_simulation command via WebSocket")
                        await start_simulation(background_tasks=None, manager=manager)
                    elif command == 'stop_simulation':
                        logger.info("Received stop_simulation command via WebSocket")
                        await stop_simulation(manager=manager)
                    else:
                        logger.warning(f"Unknown command received: {command}")
                else:
                    # Forward other messages to WebSocketManager
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

    except WebSocketDisconnect:
        logger.info(f"Client {websocket.client} disconnected normally")
    except Exception as e:
        logger.error(f"WebSocket error with {websocket.client}: {str(e)}", exc_info=True)
    finally:
        try:
            # Only attempt cleanup if connection is still active
            if websocket.client_state == WebSocketState.CONNECTED:
                try:
                    await websocket.send_json({
                        "type": "system",
                        "data": {
                            "message": "Closing connection",
                            "status": "info"
                        },
                        "timestamp": time.time()
                    })
                except:
                    pass  # Don't fail if send fails
                
                await websocket.close(code=1000)
            
            # Always clean up in manager
            await ws_manager._cleanup_connection(websocket, str(websocket.client))
        except Exception as e:
            logger.error(f"Error during WebSocket cleanup: {str(e)}", exc_info=True)
