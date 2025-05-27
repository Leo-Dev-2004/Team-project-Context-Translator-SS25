# Backend/api/endpoints.py
from fastapi import APIRouter, WebSocket, BackgroundTasks, Depends, HTTPException
import asyncio
from fastapi.websockets import WebSocketDisconnect
import asyncio
import logging
import time
import json # Ensure json is imported
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
from ..models.message_types import WebSocketMessage # Import WebSocketMessage for clearer type hints if needed

# IMPORT THE GETTER FROM YOUR DEPENDENCIES.PY FILE
from ..dependencies import get_simulation_manager

logger = logging.getLogger(__name__)
router = APIRouter()
ws_manager = WebSocketManager()


async def forward_messages_to_websocket(websocket: WebSocket, queue):
    """Continuously forward messages from queue to websocket."""
    try:
        while True:
            message = await queue.dequeue()
            if message:
                try:
                    # Ensure message is a plain dictionary before sending.
                    # This handles cases where the message might be a Pydantic model instance.
                    if isinstance(message, WebSocketMessage): # Check specifically for your Pydantic model
                        message_to_send = message.model_dump(mode='json') # Use model_dump for Pydantic v2
                    elif isinstance(message, dict): # Already a dict
                        message_to_send = message
                    else:
                        logger.error(f"Cannot serialize message of type {type(message)} from queue for WebSocket: {message}")
                        continue # Skip sending malformed message

                    # Use send_text with json.dumps for consistency with WebSocketManager.
                    await websocket.send_text(json.dumps(message_to_send))
                    logger.debug(f"Forwarded message from queue to client: {message_to_send.get('type')}")
                except Exception as e:
                    logger.error(f"Failed to send message from queue to websocket ({websocket.client}): {e}", exc_info=True)
                    break # Break if sending fails, likely connection issue
            await asyncio.sleep(0.01) # Reduce sleep slightly to 10ms to be more responsive if queues are busy
    except asyncio.CancelledError:
        logger.info(f"Message forwarding task for {websocket.client} cancelled.")
    except Exception as e:
        logger.error(f"Message forwarding task for {websocket.client} failed: {e}", exc_info=True)


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
    def format_queue_item_details(item) -> dict: # Removed dict type hint for 'item'
        """Helper to format individual queue item details for consistent output."""
        # If item is a Pydantic model, convert it to dict first
        if isinstance(item, WebSocketMessage): # Check specifically for your Pydantic model
            item = item.model_dump(mode='json') # Use model_dump for Pydantic v2
        elif isinstance(item, dict):
            pass # Already a dict
        else:
            logger.warning(f"Debug queue item is not a dict or WebSocketMessage: {type(item)}")
            return {"type": "unknown", "message": f"Non-dict/WebSocketMessage item: {str(item)}"}


        details = {
            "type": item.get('type', 'unknown'),
            "timestamp": item.get('timestamp'),
            "processing_path": item.get('processing_path', []),
            "forwarding_path": item.get('forwarding_path', []),
            # Use json.dumps to estimate size, handle potential non-serializable data gracefully
            "size_bytes": len(json.dumps(item)) if isinstance(item, dict) else 0 # Ensure it's a dict for dumps
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
    # FIX: Initialize forwarder_task to None to prevent unbound variable warning
    forwarder_task = None
    try:
        await websocket.accept()
        # Start queue forwarder task for this connection
        forwarder_task = asyncio.create_task(
            forward_messages_to_websocket(websocket, get_to_frontend_queue())
        )
        logger.info(f"WebSocket connection established from {websocket.client}")

        # Register connection with WebSocketManager IMMEDIATELY after accept
        # ws_manager will handle sending the connection_ack and managing send/receive loops
        await ws_manager.handle_connection(websocket)

        # Get simulation manager instance
        manager = get_simulation_manager(require_ready=False)

        # Main connection loop for receiving messages.
        # Note: The ws_manager._receiver task also listens for messages.
        # This loop in endpoints.py might be redundant if ws_manager._receiver is robust.
        # If ws_manager._receiver is indeed handling all incoming messages,
        # you can remove this outer while True loop and the receive_text logic here.
        # For now, let's assume it's still needed for some direct command handling.
        while True:
            try:
                # Attempt to receive a message with a timeout
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=30.0 # Timeout for receiving messages (client inactivity)
                )

                # Process received message
                # data is guaranteed to be a string here due to websocket.receive_text()
                try:
                    message_from_client = json.loads(data)
                except json.JSONDecodeError:
                    logger.error(f"Invalid JSON received from {websocket.client}: {data}")
                    await ws_manager._send_error(websocket, f"Invalid JSON format: {data[:50]}...")
                    continue # Continue to next message

                # Handle ping/pong (client-side ping handling, server can respond with pong)
                if message_from_client.get('type') == 'ping':
                    # Use send_text with json.dumps for pong response consistency
                    await websocket.send_text(json.dumps({
                        "type": "pong",
                        "timestamp": time.time()
                    }))
                    logger.debug(f"Responded with pong to {websocket.client}.")
                    continue # Don't forward ping/pong messages to ws_manager.handle_message


                # Handle specific command messages directly in endpoints if needed,
                # otherwise forward all to ws_manager.handle_message
                if message_from_client.get('type') == 'command':
                    command = message_from_client.get('data', {}).get('command') # Access command from data
                    if command == 'start_simulation':
                        logger.info(f"Received start_simulation command via WebSocket from {websocket.client}")
                        await start_simulation(background_tasks=None, manager=manager)
                    elif command == 'stop_simulation':
                        logger.info(f"Received stop_simulation command via WebSocket from {websocket.client}")
                        await stop_simulation(manager=manager)
                    else:
                        logger.warning(f"Unknown command received: {command} from {websocket.client}")
                        await ws_manager._send_error(websocket, f"Unknown command: {command}")
                else:
                    # Forward other messages to WebSocketManager for central processing
                    # ws_manager.handle_message expects raw_data (string) to parse.
                    await ws_manager.handle_message(websocket, data)


            except asyncio.TimeoutError:
                # If no message from client for 30s, this is expected.
                # Your WebSocketManager already sends pings periodically from the server side.
                logger.debug(f"No message from {websocket.client} for 30s (client inactivity timeout).")
                continue # Continue to next receive loop

            except Exception as e:
                logger.error(f"WebSocket receive/process error for {websocket.client}: {e}", exc_info=True)
                # If an error occurs here, break the loop to close the connection
                break

    except WebSocketDisconnect:
        logger.info(f"Client {websocket.client} disconnected normally from /ws endpoint")
    except Exception as e:
        logger.error(f"Unexpected WebSocket error for {websocket.client} in /ws endpoint: {str(e)}", exc_info=True)
    finally:
        # Cancel the forwarder task on disconnect/error
        if forwarder_task and not forwarder_task.done():
            forwarder_task.cancel()
            try:
                await forwarder_task # Await cancellation
            except asyncio.CancelledError:
                pass

        # The ws_manager.handle_connection method (which was awaited) takes responsibility
        # for closing the websocket and cleaning up its internal tasks (sender/receiver).
        # Therefore, we should NOT call `websocket.close()` or `ws_manager._cleanup_connection` here again.
        logger.info(f"Cleanup finished for {websocket.client} at /ws endpoint's finally block. WebSocketManager handles core connection cleanup.")