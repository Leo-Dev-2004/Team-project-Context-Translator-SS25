# Backend/services/WebSocketManager.py

import asyncio
import json
import logging
import time
import uuid
from uuid import uuid4
from pydantic import ValidationError
from fastapi import WebSocket
from fastapi.websockets import WebSocketState
from typing import Dict, Any, Optional, Union, Set
from starlette.websockets import WebSocketDisconnect

from Backend.queues.MessageQueue import MessageQueue
from Backend.models.UniversalMessage import (
    UniversalMessage,
    DeadLetterMessage,
    ProcessingPathEntry,
    ErrorTypes
)
from Backend.queues.QueueTypes import AbstractMessageQueue

logger = logging.getLogger(__name__)

class WebSocketManager:
    connections: Dict[str, WebSocket]
    active_tasks: Dict[str, tuple[asyncio.Task, ...]]
    _running: bool
    incoming_queue: AbstractMessageQueue
    websocket_out_queue: AbstractMessageQueue

    def __init__(self,
                 incoming_queue: AbstractMessageQueue,
                 outgoing_queue: AbstractMessageQueue):
        self.connections = {}
        self.active_tasks = {}
        self._running = False

        self.incoming_queue = incoming_queue
        self.outgoing_queue = outgoing_queue

        logger.info("WebSocketManager initialized. Ready to accept connections.")

    async def send_message_to_client(self, client_id: str, message: UniversalMessage):
        if message.client_id is None:
            message.client_id = client_id
        
        message.destination = "frontend"
        message.client_id = client_id

        try:
            await self.websocket_out_queue.enqueue(message)
            logger.debug(f"Queued message {message.id} for client {client_id} to websocket_out_queue.")
        except Exception as e:
            logger.error(f"Failed to enqueue message {message.id} for client {client_id} to websocket_out_queue: {e}", exc_info=True)
      

    def _get_formatted_client_address(self, websocket: WebSocket) -> str:
        client = websocket.client
        if client and hasattr(client, 'host') and hasattr(client.host, 'port'):
            return f"{client.host}:{client.port}"
        return "unknown"

    async def handle_connection(self, websocket: WebSocket, client_id: str):
        client_info = self._get_formatted_client_address(websocket)

        logger.info(f"Attempting to handle connection for {client_info} (ID: {client_id})")

        self.connections[client_id] = websocket

        try:
            await websocket.accept()
            logger.info(f"WebSocket connection accepted for {client_info} (ID: {client_id})")

            logger.info(f"Adding connection: {client_id}. Total connections: {len(self.connections)}")

            sender_task = asyncio.create_task(self._outgoing_messages_loop(client_id), name=f"ws_sender_{client_id}")
            receiver_task = asyncio.create_task(self._receiver(websocket, client_id), name=f"ws_receiver_{client_id}")

            self.active_tasks[client_id] = (receiver_task, sender_task)

            done, pending = await asyncio.wait(
                [receiver_task, sender_task],
                return_when=asyncio.FIRST_COMPLETED
            )

            for task in pending:
                logger.info(f"Cancelling pending task {task.get_name()} for {client_id}.")
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    logger.error(f"Error during cancellation of {task.get_name()} for {client_id}: {e}", exc_info=True)

            for task in done:
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    logger.error(f"Exception in completed task {task.get_name()} for {client_id}: {e}", exc_info=True)

        except WebSocketDisconnect as e:
            logger.info(f"WebSocket disconnected from {client_info} (ID: {client_id}) during handle_connection: Code {e.code}, Reason: '{e.reason}'")
        except asyncio.CancelledError:
            logger.info(f"Handle connection task for {client_info} (ID: {client_id}) was cancelled (e.g., during app shutdown).")
        except Exception as e:
            logger.critical(f"CRITICAL: Unhandled error in handle_connection for {client_info} (ID: {client_id}): {e}", exc_info=True)
            raise
        finally:
            logger.info(f"Finalizing connection handling for {client_info}. Ensuring cleanup.")
            await self.cleanup_connection(websocket, client_id)
            logger.info(f"Connection handling for {client_info} finished.")

    async def cleanup_connection(self, websocket: WebSocket, client_id: str):
        if client_id in self.active_tasks:
            tasks_to_cancel = self.active_tasks.pop(client_id)
            for task in tasks_to_cancel:
                if not task.done():
                    logger.debug(f"Cancelling cleanup task {task.get_name()} for {client_id}")
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                    except Exception as e:
                        logger.error(f"Error during cleanup task cancellation for {client_id}: {e}", exc_info=True)

        if client_id in self.connections:
            self.connections.pop(client_id, None)
            logger.info(f"Removed connection for client {client_id}. Total connections: {len(self.connections)}")

        try:
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.close()
                logger.info(f"Closed WebSocket for client {client_id}.")
        except RuntimeError as e:
            logger.warning(f"RuntimeError closing WebSocket for client {client_id} (might be already closed): {e}")
        except Exception as e:
            logger.error(f"Unexpected error during WebSocket close for client {client_id}: {e}", exc_info=True)

    async def _outgoing_messages_loop(self, client_id: str):
        logger.info(f"Starting outgoing message loop for client {client_id}.")
        try:
            while self._running:
                message: Optional[UniversalMessage] = None
                try:
                    message = await asyncio.wait_for(self.websocket_out_queue.dequeue(), timeout=0.5)
                except asyncio.TimeoutError:
                    continue

                if message is None:
                    continue

                if message.destination == "frontend" and message.client_id == client_id:
                    websocket = self.connections.get(client_id)
                    if websocket and websocket.client_state == WebSocketState.CONNECTED:
                        try:
                            # --- ADD OUTGOING MESSAGE PREPARATION DELAY HERE ---
                            outgoing_delay_seconds = 0.3 # Example: 0.3 seconds
                            # logger.debug(f"[{client_id}] Simulating {outgoing_delay_seconds}s delay before sending message {message.id}...")
                            await asyncio.sleep(outgoing_delay_seconds) # <--- ADDED DELAY

                            json_data = message.model_dump_json()
                            await websocket.send_text(json_data)
                            logger.debug(f"[{client_id}] Sent message (ID: {message.id}, Type: {message.type}) to frontend.")

                            message.processing_path.append(
                                ProcessingPathEntry(
                                    processor="WebSocketManager",
                                    status="message_sent_to_frontend",
                                    timestamp=time.time(),
                                    completed_at=time.time(),
                                    details={"websocket_status": "sent"}
                                )
                            )
                        except RuntimeError as e:
                            logger.warning(f"[{client_id}] RuntimeError sending message {message.id}: {e}. Client likely disconnected. Closing loop.", exc_info=True)
                            break
                        except Exception as e:
                            logger.error(f"[{client_id}] Failed to send message {message.id} to frontend: {e}", exc_info=True)
                    else:
                        logger.warning(f"[{client_id}] WebSocket connection not found or not active for sending message {message.id}. Sending to DLQ.")
                else:
                    logger.debug(f"[{client_id}] Message {message.id} (Dest: {message.destination}, Client: {message.client_id}) not for this sender. Re-enqueuing.")
                    await self.websocket_out_queue.enqueue(message)

        except asyncio.CancelledError:
            logger.info(f"[{client_id}] Outgoing message loop was cancelled normally.")
        except Exception as e:
            logger.critical(f"[{client_id}] CRITICAL: Outgoing message loop crashed unexpectedly: {e}", exc_info=True)
            raise
        finally:
            logger.info(f"[{client_id}] Outgoing message loop finished.")
            if client_id in self.connections:
                await self.cleanup_connection(self.connections[client_id], client_id)


    async def _receiver(self, websocket: WebSocket, client_id: str):
        msg_counter = 0
        logger.info(f"Starting receiver for client {client_id}")

        try:
            while websocket.client_state == WebSocketState.CONNECTED and self._running:
                data = None
                try:
                    logger.debug(f"[{client_id}] [Receiver {msg_counter}] Waiting for message...")
                    data = await websocket.receive_text()
                    logger.debug(f"[{client_id}] [Receiver {msg_counter}] Received raw data (first 200 chars): {data[:200]}...")
                    msg_counter += 1

                except WebSocketDisconnect as e:
                    logger.info(f"[{client_id}] WebSocket cleanly disconnected: Code {e.code}, Reason: '{e.reason}'")
                    break
                except asyncio.CancelledError:
                    logger.info(f"[{client_id}] Receiver task cancelled.")
                    break
                except RuntimeError as e:
                    logger.warning(f"[{client_id}] WebSocket runtime error during receive: {e}. Assuming disconnection.", exc_info=True)
                    break
                except Exception as recv_error:
                    logger.critical(f"[{client_id}] CRITICAL: Unexpected error receiving message: {recv_error}", exc_info=True)
                    await asyncio.sleep(0.1)
                    continue

                if data:
                    raw_message_dict: Dict[str, Any] = {}
                    try:
                        logger.debug(f"[{client_id}] [Receiver {msg_counter}] Parsing JSON.")
                        raw_message_dict = json.loads(data)
                        logger.debug(f"[{client_id}] [Receiver {msg_counter}] Parsed JSON (first 500 chars): {json.dumps(raw_message_dict, indent=2)[:500]}...")

                        universal_message = UniversalMessage.model_validate(raw_message_dict)

                        if not universal_message.client_id:
                            universal_message.client_id = client_id
                            logger.debug(f"[{client_id}] Assigned client_id to UniversalMessage.")
                        elif universal_message.client_id != client_id:
                            logger.warning(f"[{client_id}] Incoming message client_id ({universal_message.client_id}) "
                                           f"does not match connection ID. Overriding to {client_id}.")
                            universal_message.client_id = client_id

                        universal_message.origin = "frontend"
                        universal_message.destination = "backend.dispatcher"

                        universal_message.processing_path.append(
                            ProcessingPathEntry(
                                processor="WebSocketManager_Receiver",
                                status="received_from_frontend",
                                timestamp=time.time(),
                                completed_at=time.time(),
                                details={"client_id": client_id}
                            )
                        )

                        # --- ADD INCOMING MESSAGE PROCESSING DELAY HERE ---
                        processing_delay_seconds = 0.5 # Example: 0.5 seconds
                        # logger.debug(f"[{client_id}] Simulating {processing_delay_seconds}s processing delay before enqueueing message {universal_message.id}...")
                        await asyncio.sleep(processing_delay_seconds) # <--- ADDED DELAY

                        logger.debug(f"[{client_id}] Validated UniversalMessage (ID: {universal_message.id}, Type: {universal_message.type}) from client. Enqueuing.")

                    except json.JSONDecodeError as e:
                        logger.error(f"[{client_id}] [Receiver {msg_counter}] Invalid JSON received: {e}\nRaw data: {data[:200]}...", exc_info=True)
                       
                        continue
                    except ValidationError as e:
                        logger.error(f"[{client_id}] [Receiver {msg_counter}] Pydantic validation error for incoming message (UniversalMessage schema): {e.errors()}\nRaw dict: {raw_message_dict}", exc_info=True)
                       
                        continue
                    except Exception as e:
                        logger.critical(f"[{client_id}] [Receiver {msg_counter}] CRITICAL: Unexpected error during message parsing/validation: {e}\nRaw data: {data[:200]}...", exc_info=True)
                     
                        continue

                    try:
                        logger.debug(f"[{client_id}] [Receiver {msg_counter}] Enqueueing message {universal_message.id} of type '{universal_message.type}' to incoming_queue.")
                        await self.incoming_queue.enqueue(universal_message)
                    except Exception as e:
                        logger.error(f"[{client_id}] [Receiver {msg_counter}] Failed to enqueue message {universal_message.id} to incoming_queue: {e}", exc_info=True)
                        await asyncio.sleep(0.1)

        except asyncio.CancelledError:
            logger.info(f"[{client_id}] Receiver task was cancelled normally.")
        except Exception as e:
            logger.critical(f"[{client_id}] CRITICAL: Receiver task crashed unexpectedly: {e}", exc_info=True)
            raise
        finally:
            logger.info(f"[{client_id}] Receiver task finished.")
            if client_id in self.connections:
                await self.cleanup_connection(self.connections[client_id], client_id)

    async def start(self):
        if not self._running:
            self._running = True
            logger.info("WebSocketManager global running flag set to True.")
        else:
            logger.info("WebSocketManager is already running.")

    async def stop(self):
        logger.info("Initiating WebSocketManager shutdown...")
        self._running = False

        tasks_to_cancel: Set[asyncio.Task] = set()
        for client_id, tasks_tuple in list(self.active_tasks.items()):
            for task in tasks_tuple:
                if not task.done():
                    tasks_to_cancel.add(task)
            self.active_tasks.pop(client_id)

        if tasks_to_cancel:
            logger.info(f"Cancelling {len(tasks_to_cancel)} active WebSocketManager tasks.")
            for task in tasks_to_cancel:
                task.cancel()
            await asyncio.gather(*tasks_to_cancel, return_exceptions=True)
            logger.info("All WebSocketManager background tasks processed during shutdown.")

        connected_websockets = list(self.connections.values())
        self.connections.clear()

        if connected_websockets:
            logger.info(f"Closing {len(connected_websockets)} active WebSocket connections.")
            await asyncio.gather(*[ws.close() for ws in connected_websockets if ws.client_state == WebSocketState.CONNECTED], return_exceptions=True)
            logger.info("All WebSocket connections closed.")

        logger.info("WebSocketManager shutdown complete. All client connections and tasks cleared.")