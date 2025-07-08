# Backend/services/WebSocketManager.py (Revised)

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

from Backend.queues.MessageQueue import MessageQueue # Assuming this is your concrete implementation
from Backend.models.UniversalMessage import (
    UniversalMessage,
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
    # IMPORTANT: The websocket_out_queue needs to be the same instance
    # that the BackendServiceDispatcher enqueues messages to.
    # It should probably be passed in here or be a globally accessible queue instance.
    websocket_out_queue: AbstractMessageQueue # This needs to be correctly initialized for sending messages to frontend

    def __init__(self,
                 incoming_queue: AbstractMessageQueue,
                 # Make sure this outgoing_queue is the one your dispatcher uses to send to frontend
                 outgoing_queue: AbstractMessageQueue): # Renamed for clarity
        self.connections = {}
        self.active_tasks = {}
        self._running = False

        self.incoming_queue = incoming_queue
        # Assign the queue that the BackendServiceDispatcher pushes messages to for the frontend
        self.websocket_out_queue = outgoing_queue

        logger.info("WebSocketManager initialized. Ready to accept connections.")

    async def send_message_to_client(self, client_id: str, message: UniversalMessage):
        """
        Public method for other services (e.g., BackendServiceDispatcher) to send messages to a specific client.
        This simply enqueues the message to the internal websocket_out_queue.
        """
        # Ensure client_id is set for routing within _outgoing_messages_loop
        if message.client_id is None:
            message.client_id = client_id
        
        # Ensure destination is frontend
        message.destination = "frontend"
        
        try:
            # Enqueue to the dedicated queue for outgoing WebSocket messages
            await self.websocket_out_queue.enqueue(message)
            # logger.debug(f"Queued message {message.id} for client {client_id} to websocket_out_queue.")
        except Exception as e:
            logger.error(f"Failed to enqueue message {message.id} for client {client_id} to websocket_out_queue: {e}", exc_info=True)
      
    def _get_formatted_client_address(self, websocket: WebSocket) -> str:
        client = websocket.client
        if client and client.host and client.port: # Corrected attribute access
            return f"{client.host}:{client.port}"
        return "unknown"

    async def handle_connection(self, websocket: WebSocket, client_id: str):
        client_info = self._get_formatted_client_address(websocket)

        logger.info(f"Attempting to handle connection for {client_info} (ID: {client_id})")

        # Add connection *before* accept to ensure it's tracked even if accept fails
        self.connections[client_id] = websocket

        receiver_task = None
        sender_task = None

        try:
            await websocket.accept()
            logger.info(f"WebSocket connection accepted for {client_info} (ID: {client_id})")
            logger.info(f"Adding connection: {client_id}. Total connections: {len(self.connections)}")

            sender_task = asyncio.create_task(self._outgoing_messages_loop(client_id), name=f"ws_sender_{client_id}")
            receiver_task = asyncio.create_task(self._receiver(websocket, client_id), name=f"ws_receiver_{client_id}")

            self.active_tasks[client_id] = (receiver_task, sender_task)

            # Wait for both tasks. If one completes, the other will be cancelled.
            done, pending = await asyncio.wait(
                [receiver_task, sender_task],
                return_when=asyncio.FIRST_COMPLETED # Or asyncio.ALL_COMPLETED if you want both to finish naturally
            )

            # Important: Cancel pending tasks and await them to ensure they clean up
            for task in pending:
                if not task.done(): # Only cancel if not already done
                    logger.info(f"Cancelling pending task {task.get_name()} for {client_id}.")
                    task.cancel()
                    try:
                        await task # Await to propagate CancelledError and ensure task exits
                    except asyncio.CancelledError:
                        logger.debug(f"Task {task.get_name()} for {client_id} cancelled gracefully.")
                    except Exception as e:
                        logger.error(f"Error awaiting cancelled task {task.get_name()} for {client_id}: {e}", exc_info=True)

            # Check results of tasks that completed
            for task in done:
                try:
                    await task # Await to propagate any exceptions that caused it to complete
                except asyncio.CancelledError:
                    logger.debug(f"Task {task.get_name()} for {client_id} was already cancelled and completed.")
                except Exception as e:
                    logger.error(f"Exception in completed task {task.get_name()} for {client_id}: {e}", exc_info=True)

        except WebSocketDisconnect as e:
            logger.info(f"WebSocket disconnected from {client_info} (ID: {client_id}) during handle_connection: Code {e.code}, Reason: '{e.reason}'")
        except asyncio.CancelledError:
            logger.info(f"Handle connection task for {client_info} (ID: {client_id}) was cancelled (e.g., during app shutdown).")
        except Exception as e:
            logger.critical(f"CRITICAL: Unhandled error in handle_connection for {client_info} (ID: {client_id}): {e}", exc_info=True)
            # Re-raise to ensure SystemRunner catches it and performs full shutdown
            raise
        finally:
            logger.info(f"Finalizing connection handling for {client_info}. Ensuring cleanup.")
            # Centralized cleanup. Only call once.
            await self.cleanup_connection(websocket, client_id)
            logger.info(f"Connection handling for {client_info} finished.")

    async def cleanup_connection(self, websocket: WebSocket, client_id: str):
        # Remove tasks from active_tasks first to prevent re-cancellation in loops
        tasks_to_cancel = self.active_tasks.pop(client_id, None)

        if tasks_to_cancel:
            for task in tasks_to_cancel:
                if not task.done():
                    logger.debug(f"Cancelling cleanup task {task.get_name()} for {client_id}")
                    task.cancel()
                    try:
                        await task # Await here to ensure it truly finishes
                    except asyncio.CancelledError:
                        pass # Expected if we just cancelled it
                    except Exception as e:
                        logger.error(f"Error during cleanup task cancellation for {client_id}: {e}", exc_info=True)

        # Remove websocket from connections dictionary
        if client_id in self.connections:
            del self.connections[client_id] # Use del for explicit removal
            logger.info(f"Removed connection for client {client_id}. Total connections: {len(self.connections)}")

        # Attempt to close the websocket, but only if it's still connected
        try:
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.close()
                logger.info(f"Closed WebSocket for client {client_id}.")
            elif websocket.client_state == WebSocketState.DISCONNECTED:
                logger.debug(f"WebSocket for client {client_id} was already disconnected.")
            else: # E.g., WebSocketState.CLOSING or other states
                logger.info(f"WebSocket for client {client_id} is in state {websocket.client_state.name}, no explicit close needed.")

        except RuntimeError as e:
            # This can happen if the websocket is already in the process of closing
            # or if the underlying connection is already gone.
            logger.warning(f"RuntimeError closing WebSocket for client {client_id} (might be already closed): {e}")
        except Exception as e:
            logger.error(f"Unexpected error during WebSocket close for client {client_id}: {e}", exc_info=True)

    async def _outgoing_messages_loop(self, client_id: str):
        logger.info(f"Starting outgoing message loop for client {client_id}.")
        websocket = self.connections.get(client_id)
        if not websocket:
            logger.warning(f"Outgoing loop started for {client_id}, but WebSocket not found in connections. Exiting.")
            return

        try:
            # Loop while the manager is running and the websocket is connected
            while self._running and websocket.client_state == WebSocketState.CONNECTED:
                message: Optional[UniversalMessage] = None
                try:
                    # Dequeue messages intended for this specific client_id
                    # The queue might contain messages for other clients if it's a shared queue
                    # We only dequeue if it's for this client or is a general broadcast (if you add that logic)
                    message = await asyncio.wait_for(self.websocket_out_queue.dequeue(), timeout=0.5)

                    if message and (message.client_id == client_id or message.client_id is None): # Added client_id check
                        # If message.client_id is None, treat as broadcast or for the first connected client
                        # You might want more sophisticated routing if you have multiple clients
                        pass
                    else:
                        # This message is not for this client, re-enqueue or discard
                        if message:
                            await self.websocket_out_queue.enqueue(message) # Put it back for another sender to pick up
                            logger.debug(f"[{client_id}] Message {message.id} (Dest: {message.destination}, Client: {message.client_id}) not for this sender. Re-enqueuing.")
                        continue # Continue to next loop iteration

                except asyncio.TimeoutError:
                    continue # No message in queue, continue loop
                except asyncio.CancelledError:
                    logger.info(f"[{client_id}] Outgoing message loop received cancellation signal during dequeue.")
                    break # Exit loop cleanly
                except Exception as e:
                    logger.error(f"[{client_id}] Error dequeuing message from websocket_out_queue: {e}", exc_info=True)
                    await asyncio.sleep(0.1) # Prevent busy-waiting
                    continue # Continue loop


                if message: # Ensure message is not None before proceeding
                    # Re-check connection state right before sending
                    if websocket.client_state != WebSocketState.CONNECTED:
                        logger.warning(f"[{client_id}] WebSocket disconnected before sending message {message.id}. Breaking loop.")
                        break # Exit loop if connection is no longer active

                    try:
                        # --- ADD OUTGOING MESSAGE PREPARATION DELAY HERE ---
                        outgoing_delay_seconds = 0.3 # Example: 0.3 seconds
                        # logger.debug(f"[{client_id}] Simulating {outgoing_delay_seconds}s delay before sending message {message.id}...")
                        await asyncio.sleep(outgoing_delay_seconds) # <--- ADDED DELAY

                        json_data = message.model_dump_json()
                        await websocket.send_text(json_data)
                        # logger.debug(f"[{client_id}] Sent message (ID: {message.id}, Type: {message.type}) to frontend.")   # IMPORTANT

                        message.processing_path.append(
                            ProcessingPathEntry(
                                processor="WebSocketManager",
                                status="message_sent_to_frontend",
                                timestamp=time.time(),
                                completed_at=time.time(),
                                details={"websocket_status": "sent"}
                            )
                        )
                    except (RuntimeError, WebSocketDisconnect) as e:
                        # Catch specific exceptions that mean the connection is gone
                        logger.warning(f"[{client_id}] Connection error sending message {message.id}: {e}. Client likely disconnected. Closing loop.", exc_info=True)
                        break # Exit the loop if send fails due to connection issues
                    except Exception as e:
                        logger.error(f"[{client_id}] Failed to send message {message.id} to frontend: {e}", exc_info=True)
                        # Decide what to do with the message here: retry? log to dead letter?
                        # For now, just log and continue, hoping the next attempt works or connection closes.

        except asyncio.CancelledError:
            logger.info(f"[{client_id}] Outgoing message loop was cancelled normally.")
        except Exception as e:
            logger.critical(f"[{client_id}] CRITICAL: Outgoing message loop crashed unexpectedly: {e}", exc_info=True)
            raise
        finally:
            logger.info(f"[{client_id}] Outgoing message loop finished for {client_id}.")
            # Do NOT call cleanup_connection here. Let handle_connection manage cleanup.

    async def _receiver(self, websocket: WebSocket, client_id: str):
        msg_counter = 0
        logger.info(f"Starting receiver for client {client_id}")

        try:
            # Loop while the manager is running and the websocket is connected
            while self._running and websocket.client_state == WebSocketState.CONNECTED:
                data = None
                try:
                    logger.debug(f"[{client_id}] [Receiver {msg_counter}] Waiting for message...")
                    data = await websocket.receive_text()
                    logger.debug(f"[{client_id}] [Receiver {msg_counter}] Received raw data (first 200 chars): {data[:200]}...")
                    msg_counter += 1

                except WebSocketDisconnect as e:
                    logger.info(f"[{client_id}] WebSocket cleanly disconnected: Code {e.code}, Reason: '{e.reason}'")
                    break # Exit loop on disconnect
                except asyncio.CancelledError:
                    logger.info(f"[{client_id}] Receiver task cancelled.")
                    break # Exit loop on cancellation
                except RuntimeError as e:
                    logger.warning(f"[{client_id}] WebSocket runtime error during receive: {e}. Assuming disconnection.", exc_info=True)
                    break # Exit loop on runtime error (often indicates underlying connection issue)
                except Exception as recv_error:
                    logger.critical(f"[{client_id}] CRITICAL: Unexpected error receiving message: {recv_error}", exc_info=True)
                    await asyncio.sleep(0.1)
                    continue # Try again after short delay

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

                        universal_message.origin = "frontend" # Or "stt" if you want to be more specific
                        universal_message.destination = "backend.dispatcher" # Destination for this message

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

                        logger.debug(f"[{client_id}] [Receiver {msg_counter}] Enqueueing message {universal_message.id} of type '{universal_message.type}' to incoming_queue.")
                        await self.incoming_queue.enqueue(universal_message)

                    except json.JSONDecodeError as e:
                        logger.error(f"[{client_id}] [Receiver {msg_counter}] Invalid JSON received: {e}\nRaw data: {data[:200]}...", exc_info=True)
                        # Consider sending an error message back to client if possible/desired
                        continue
                    except ValidationError as e:
                        logger.error(f"[{client_id}] [Receiver {msg_counter}] Pydantic validation error for incoming message (UniversalMessage schema): {e.errors()}\nRaw dict: {raw_message_dict}", exc_info=True)
                        # Consider sending an error message back to client if possible/desired
                        continue
                    except Exception as e:
                        logger.critical(f"[{client_id}] [Receiver {msg_counter}] CRITICAL: Unexpected error during message parsing/validation: {e}\nRaw data: {data[:200]}...", exc_info=True)
                        # Log, but don't crash the receiver loop for unhandled errors during parsing
                        continue

        except asyncio.CancelledError:
            logger.info(f"[{client_id}] Receiver task was cancelled normally.")
        except Exception as e:
            logger.critical(f"[{client_id}] CRITICAL: Receiver task crashed unexpectedly: {e}", exc_info=True)
            raise # Re-raise to ensure handle_connection catches it
        finally:
            logger.info(f"[{client_id}] Receiver task finished for {client_id}.")
            # Do NOT call cleanup_connection here. Let handle_connection manage cleanup.

    async def start(self):
        if not self._running:
            self._running = True
            logger.info("WebSocketManager global running flag set to True.")
        else:
            logger.info("WebSocketManager is already running.")

    async def stop(self):
        logger.info("Initiating WebSocketManager shutdown...")
        self._running = False # Signal loops to stop

        tasks_to_cancel: Set[asyncio.Task] = set()
        # Iterate over a copy of self.active_tasks to avoid RuntimeError during modification
        for client_id, tasks_tuple in list(self.active_tasks.items()):
            for task in tasks_tuple:
                if not task.done():
                    tasks_to_cancel.add(task)
            # Remove client's tasks from dict immediately to prevent double handling
            self.active_tasks.pop(client_id, None) 

        if tasks_to_cancel:
            logger.info(f"Cancelling {len(tasks_to_cancel)} active WebSocketManager tasks.")
            # Use gather with return_exceptions=True to allow all tasks to attempt cancellation
            # and avoid stopping on the first exception.
            await asyncio.gather(*tasks_to_cancel, return_exceptions=True)
            logger.info("All WebSocketManager background tasks processed during shutdown.")

        # Gather all current websocket connections for closing
        connected_websockets = list(self.connections.values())
        self.connections.clear() # Clear the connections dictionary

        if connected_websockets:
            logger.info(f"Closing {len(connected_websockets)} active WebSocket connections.")
            # Close only if still connected, and use gather for concurrent closing
            await asyncio.gather(*[
                ws.close() for ws in connected_websockets
                if ws.client_state == WebSocketState.CONNECTED
            ], return_exceptions=True)
            logger.info("All WebSocket connections closed.")

        logger.info("WebSocketManager shutdown complete. All client connections and tasks cleared.")