# Backend/services/WebSocketManager.py (Refactored)

import asyncio
import json
import logging
import time
from typing import Dict, Optional
from starlette.websockets import WebSocket, WebSocketDisconnect, WebSocketState
from pydantic import ValidationError

from ..models.UniversalMessage import UniversalMessage, ProcessingPathEntry
from ..queues.QueueTypes import AbstractMessageQueue

logger = logging.getLogger(__name__)

class WebSocketManager:
    def __init__(self, incoming_queue: AbstractMessageQueue, outgoing_queue: AbstractMessageQueue):
        self.connections: Dict[str, WebSocket] = {}
        self.client_tasks: Dict[str, asyncio.Task] = {} # Nur noch ein Task pro Client (Receiver)
        self.incoming_queue = incoming_queue
        self.websocket_out_queue = outgoing_queue
        self._dispatcher_task: Optional[asyncio.Task] = None
        logger.info("WebSocketManager initialized.")

    async def start(self):
        """Starts the central message dispatcher task."""
        if not self._dispatcher_task:
            self._dispatcher_task = asyncio.create_task(self._message_dispatcher())
            logger.info("WebSocketManager central message dispatcher started.")

    async def stop(self):
        """Stops all tasks and closes all connections."""
        logger.info("Initiating WebSocketManager shutdown...")

        # 1. Stop the central dispatcher from accepting new messages
        if self._dispatcher_task:
            self._dispatcher_task.cancel()
            try:
                await self._dispatcher_task
            except asyncio.CancelledError:
                logger.info("Message dispatcher task cancelled gracefully.")
        
        # 2. Cancel all active client receiver tasks
        for task in self.client_tasks.values():
            task.cancel()
        if self.client_tasks:
            await asyncio.gather(*self.client_tasks.values(), return_exceptions=True)
            logger.info("All client receiver tasks cancelled.")
        
        # 3. Close all remaining WebSocket connections
        for ws in self.connections.values():
            if ws.client_state == WebSocketState.CONNECTED:
                await ws.close(code=1001, reason="Server is shutting down")
        
        self.connections.clear()
        self.client_tasks.clear()
        logger.info("WebSocketManager shutdown complete.")

    async def handle_connection(self, websocket: WebSocket, client_id: str):
        """Accepts a new connection and starts a receiver task for it."""
        await websocket.accept()
        self.connections[client_id] = websocket
        if websocket.client is not None:
            client_info = f"{websocket.client.host}:{websocket.client.port}"
        else:
            client_info = "unknown"
        logger.info(f"Connection accepted for {client_info} (ID: {client_id}). Total: {len(self.connections)}")

        receiver_task = asyncio.create_task(self._receiver(websocket, client_id))
        self.client_tasks[client_id] = receiver_task

        try:
            await receiver_task # Wait for the receiver to finish (e.g., on disconnect)
        except asyncio.CancelledError:
            logger.info(f"Receiver task for {client_id} was cancelled.")
        finally:
            # Cleanup is handled here when a single client disconnects
            if client_id in self.connections:
                del self.connections[client_id]
            if client_id in self.client_tasks:
                del self.client_tasks[client_id]
            logger.info(f"Connection for {client_id} cleaned up. Remaining connections: {len(self.connections)}")

    # NEU: Der zentrale "Postmaster" Task
    async def _message_dispatcher(self):
        """
        Continuously reads from the outgoing queue and sends messages to the correct client.
        """
        logger.info("Message dispatcher loop started.")
        while True:
            try:
                message = await self.websocket_out_queue.dequeue()
                client_id = message.destination # Wir nehmen an, die Nachricht hat jetzt ein klares Ziel

                if client_id is not None:
                    websocket = self.connections.get(client_id)
                    if websocket and websocket.client_state == WebSocketState.CONNECTED:
                        try:
                            await websocket.send_text(message.model_dump_json())
                            logger.debug(f"Dispatched message '{message.type}' to client {client_id}")
                        except (WebSocketDisconnect, RuntimeError) as e:
                            logger.warning(f"Failed to send message to client {client_id} (disconnected): {e}")
                            # Die Cleanup-Logik in handle_connection wird den Client entfernen
                    else:
                        logger.warning(f"Could not dispatch message: Client '{client_id}' not found or not connected.")
                else:
                    logger.warning("Could not dispatch message: 'client_id' is None.")

            except asyncio.CancelledError:
                logger.info("Message dispatcher loop stopped.")
                break
            except Exception as e:
                logger.error(f"Error in message dispatcher loop: {e}", exc_info=True)
                await asyncio.sleep(1) # Prevent fast error loops

    async def _receiver(self, websocket: WebSocket, client_id: str):
        """Listens for incoming messages from a single client."""
        try:
            while True:
                data = await websocket.receive_text()
                try:
                    raw_message = json.loads(data)
                    message = UniversalMessage.model_validate(raw_message)
                    
                    # Stellt sicher, dass die Metadaten korrekt sind
                    message.client_id = client_id
                    message.origin = "websocket" # oder spezifischer, z.B. client_id
                    
                    message.processing_path.append(ProcessingPathEntry(
                        processor="WebSocketManager_Receiver",
                        status="received",
                        timestamp=time.time(),
                        completed_at=None,
                        details=None
                    ))
                    
                    await self.incoming_queue.enqueue(message)
                    logger.debug(f"Received and enqueued message '{message.type}' from {client_id}")

                except json.JSONDecodeError:
                    logger.warning(f"Received invalid JSON from {client_id}: {data[:200]}")
                except ValidationError as e:
                    logger.warning(f"Received message from {client_id} that failed validation: {e}")

        except WebSocketDisconnect:
            logger.info(f"Client {client_id} disconnected.")
        except asyncio.CancelledError:
            logger.info(f"Receiver for {client_id} cancelled.")
        except Exception as e:
            logger.error(f"Unexpected error in receiver for {client_id}: {e}", exc_info=True)
        finally:
            # Die Cleanup-Logik wird in handle_connection ausgelöst, wenn dieser Task endet.
            pass