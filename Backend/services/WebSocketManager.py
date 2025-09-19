import asyncio
import json
import logging
import time
from typing import Dict, Optional, List

from pydantic import ValidationError
from starlette.websockets import WebSocket, WebSocketDisconnect, WebSocketState

from ..models.UniversalMessage import UniversalMessage, ProcessingPathEntry
from ..queues.QueueTypes import AbstractMessageQueue

logger = logging.getLogger(__name__)

class WebSocketManager:
    def __init__(self, incoming_queue: AbstractMessageQueue, outgoing_queue: AbstractMessageQueue):
        self.connections: Dict[str, WebSocket] = {}
        self.client_tasks: Dict[str, asyncio.Task] = {}
        self.user_session_map: Dict[str, str] = {}
        self.incoming_queue = incoming_queue
        self.websocket_out_queue = outgoing_queue
        self._dispatcher_task: Optional[asyncio.Task] = None
        logger.info("WebSocketManager initialized.")

    async def start(self):
        if not self._dispatcher_task:
            self._dispatcher_task = asyncio.create_task(self._message_dispatcher())
            logger.info("WebSocketManager central message dispatcher started.")

    async def stop(self):
        """
        Gracefully stops the WebSocketManager by closing all connections
        and stopping background tasks.
        """
        logger.info("Initiating WebSocketManager shutdown...")
        
        # Cancel the main dispatcher task first to stop processing new outgoing messages.
        if self._dispatcher_task:
            self._dispatcher_task.cancel()
            try:
                # Await the task to ensure it has a chance to clean up.
                await self._dispatcher_task
            except asyncio.CancelledError:
                pass # This is expected behavior
            self._dispatcher_task = None
            logger.info("Central message dispatcher stopped.")

        # Iterate through a copy of the client_tasks dictionary to avoid issues
        # with dictionary size changes during the loop.
        tasks_to_cancel = list(self.client_tasks.values())
        if tasks_to_cancel:
            logger.info(f"Cancelling {len(tasks_to_cancel)} client receiver tasks...")
            for task in tasks_to_cancel:
                task.cancel()
            
            # Gather all cancellation tasks to ensure they are all processed
            # before continuing.
            await asyncio.gather(*tasks_to_cancel, return_exceptions=True)
            self.client_tasks.clear()
            
        # Finally, close all WebSocket connections.
        connections_to_close = list(self.connections.values())
        if connections_to_close:
            logger.info(f"Closing {len(connections_to_close)} WebSocket "
                       f"connections...")
            for ws in connections_to_close:
                # Attempt to close the WebSocket connection with code=1000.
                # If the connection is in an unexpected state, log the error
                # and continue.
                try:
                    await ws.close(code=1000)
                except Exception as e:
                    logger.error(f"Error closing WebSocket connection: {e}",
                               exc_info=True)
        
        self.connections.clear()
        self.user_session_map.clear()
        
        logger.info("WebSocketManager shutdown complete. All tasks and connections are closed.")

    def associate_user_session(self, client_id: str, user_session_id: str):
        """Stores the link between a client_id and a user_session_id."""
        self.user_session_map[client_id] = user_session_id
        logger.info(f"Associated client {client_id} with User Session ID {user_session_id}.")

    async def handle_connection(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.connections[client_id] = websocket
        client_info = f"{websocket.client.host}:{websocket.client.port}" if websocket.client else "unknown"
        logger.info(f"Connection accepted for {client_info} (ID: {client_id}). Total: {len(self.connections)}")

        receiver_task = asyncio.create_task(self._receiver(websocket, client_id))
        self.client_tasks[client_id] = receiver_task

        try:
            await receiver_task
        except asyncio.CancelledError:
            logger.info(f"Receiver task for {client_id} was cancelled.")
        finally:
            # Cleanup
            if client_id in self.connections: del self.connections[client_id]
            if client_id in self.client_tasks: del self.client_tasks[client_id]
            # HINZUGEFÜGT: Bereinigung der Session-Map bei Disconnect
            if client_id in self.user_session_map: del self.user_session_map[client_id]
            logger.info(f"Connection for {client_id} cleaned up.")
            
    async def _message_dispatcher(self):
        """Reads from the outgoing queue and dispatches messages to clients or groups."""
        logger.info("Message dispatcher loop started.")
        while True:
            try:
                message = await self.websocket_out_queue.dequeue()
                destination = message.destination

                # Case 1: Message is for a specific, connected client ID
                if destination and destination in self.connections:
                    await self._send_to_websocket(self.connections[destination], message)
                    logger.debug(f"Dispatched message '{message.type}' to client {destination}")

                # Case 2: Message is for the group of all frontend clients
                elif destination == "all_frontends":
                    frontend_clients = [
                        ws for cid, ws in self.connections.items() if cid.startswith("frontend_")
                    ]
                    if frontend_clients:
                        logger.debug(f"Broadcasting message '{message.type}' to {len(frontend_clients)} frontend clients.")
                        send_tasks = [self._send_to_websocket(ws, message) for ws in frontend_clients]
                        await asyncio.gather(*send_tasks)
                
                else:
                    logger.warning(f"Could not dispatch message: Destination '{destination}' not found or not a valid group.")

            except asyncio.CancelledError:
                logger.info("Message dispatcher loop stopped.")
                break
            except Exception as e:
                logger.error(f"Error in message dispatcher loop: {e}", exc_info=True)
                await asyncio.sleep(1)

    async def _send_to_websocket(self, websocket: WebSocket, message: UniversalMessage):
        """Safely sends a message to a single WebSocket connection."""
        try:
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.send_text(message.model_dump_json())
        except (WebSocketDisconnect, RuntimeError) as e:
            # This is a non-critical error that happens when a client disconnects mid-send
            client_id = next((cid for cid, ws in self.connections.items() if ws is websocket), "unknown")
            logger.warning(f"Failed to send to client {client_id} (likely disconnected): {e}")

    async def _receiver(self, websocket: WebSocket, client_id: str):
        """Listens for incoming messages from a single client."""
        try:
            while True:
                data = await websocket.receive_text()
                try:
                    message = UniversalMessage.model_validate(json.loads(data))
                    
                    # Ensure metadata is correctly assigned
                    message.client_id = client_id
                    message.origin = "websocket_client"
                    
                    message.processing_path.append(ProcessingPathEntry(
                        processor="WebSocketManager_Receiver",
                        status="received",
                        timestamp=time.time(),
                        completed_at=time.time(),
                        details=dict(client_id=client_id, websocket_state=websocket.client_state.name)
                    ))
                    
                    await self.incoming_queue.enqueue(message)
                    logger.debug(f"Received and enqueued message '{message.type}' from {client_id}")

                except (json.JSONDecodeError, ValidationError) as e:
                    logger.warning(f"Received invalid message from {client_id}: {e}")

        except WebSocketDisconnect:
            logger.info(f"Client {client_id} disconnected.")
        except asyncio.CancelledError:
            pass  # Normal during a graceful shutdown
        except Exception as e:
            logger.error(f"Unexpected error in receiver for {client_id}: {e}", exc_info=True)