import asyncio
import json
import logging
import time
import uuid
from uuid import uuid4
from pydantic import ValidationError
from fastapi import WebSocket
from fastapi.websockets import WebSocketState
from typing import Dict, Any, Optional, Union
from starlette.websockets import WebSocketDisconnect

from Backend.models.message_types import UniversalMessage, DeadLetterMessage
from Backend.core.Queues import queues

logger = logging.getLogger(__name__)

class WebSocketManager:
    def __init__(self):
        self.connections: Dict[str, WebSocket] = {} # Store connections by client_id
        self.active_tasks: Dict[str, tuple[asyncio.Task, ...]] = {} # Will store (receiver_task, sender_task)
        self._running = True  # Flag for graceful shutdown

        assert queues.incoming is not None, "Incoming queue not initialized!"
        self.incoming_queue = queues.incoming

        # OUTGOING QUEUE REFERENCE - NOW UNCOMMENTED
        assert queues.websocket_out is not None, "WebSocket Outgoing queue not initialized!"
        self.websocket_out_queue = queues.websocket_out # This queue is specifically for messages going *out* via WS
        
        assert queues.dead_letter is not None, "Dead letter queue not initialized!"
        self.dead_letter_queue = queues.dead_letter

    def _get_formatted_client_address(self, websocket: WebSocket) -> str:
        client = websocket.client
        if client and hasattr(client, 'host') and hasattr(client, 'port'):
            return f"{client.host}:{client.port}"
        return "unknown"

    async def _send_to_dead_letter_queue(self, original_message: Union[dict, UniversalMessage], 
                                       reason: str, client_id: Optional[str] = None, error_type: Optional[str] = None,
                                       error_details: Optional[Union[str, Dict[str, Any]]] = None):
        """Helper to send messages to the Dead Letter Queue.
        Adjusted to handle UniversalMessage.
        """
        try:
            if isinstance(original_message, UniversalMessage):
                original_message_dict = original_message.model_dump()
            elif isinstance(original_message, dict):
                original_message_dict = original_message
            else:
                original_message_dict = {"raw_message_string": str(original_message)}

            details = {
                "type": error_type or "websocket_manager_error",
                "message": reason,
                "component": "WebSocketManager",
                "timestamp": time.time(),
                "client_id": client_id or "N/A"
            }
            if isinstance(error_details, dict):
                details.update(error_details)
            elif isinstance(error_details, str):
                details["additional_details"] = error_details

            dl_message = DeadLetterMessage(
                id=str(uuid4()),
                type="system.dead_letter",
                client_id=client_id,
                payload={"original_message_data": original_message_dict,
                         "reason": reason,
                         "error_details": details},
                original_message=original_message_dict,
                reason=reason,
                error_details=details,
                timestamp=time.time()
            )
            
            await self.dead_letter_queue.enqueue(dl_message)
            logger.error(f"Message sent to DLQ (reason: {reason}) for client: {client_id}")
        except Exception as e:
            logger.critical(f"CRITICAL: Failed to send message to Dead Letter Queue within WebSocketManager: {e}\nOriginal: {original_message}", exc_info=True)

    async def handle_connection(self, websocket: WebSocket, client_id: str):
        """Handle new WebSocket connection"""
        client_info = self._get_formatted_client_address(websocket)
        
        logger.info(f"Attempting to handle connection for {client_info} (ID: {client_id})")

        try:
            await websocket.accept()
            logger.info(f"WebSocket connection accepted for {client_info} (ID: {client_id})")
            
            self.connections[client_id] = websocket 
            logger.info(f"Adding connection: {client_id}. Total connections: {len(self.connections)}")
            
            receiver_task = asyncio.create_task(self._receiver(websocket, client_id), name=f"receiver_{client_id}")
            # UNCOMMENTED: Start the sender task
            sender_task = asyncio.create_task(self._outgoing_messages_loop(client_id), name=f"sender_{client_id}")

            self.active_tasks[client_id] = (receiver_task, sender_task) # Store both tasks

            # Wait for either task to complete, indicating a disconnect or error
            done, pending = await asyncio.wait(
                [receiver_task, sender_task], 
                return_when=asyncio.FIRST_COMPLETED
            )

            # If one task finishes, ensure cleanup of the other and connection
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
                    raise

        except WebSocketDisconnect as e:
            logger.info(f"WebSocket disconnected from {client_info} (ID: {client_id}) during handle_connection: Code {e.code}, Reason: '{e.reason}'")
        except asyncio.CancelledError:
            logger.info(f"Handle connection task for {client_info} (ID: {client_id}) was cancelled.")
        except Exception as e:
            logger.critical(f"CRITICAL: Unhandled error in handle_connection for {client_info} (ID: {client_id}): {e}", exc_info=True)
            raise 
        finally:
            logger.info(f"Finalizing connection handling for {client_info}. Ensuring cleanup.")
            await self.cleanup_connection(websocket, client_id)
            logger.info(f"Connection handling for {client_info} finished.")

    async def cleanup_connection(self, websocket: WebSocket, client_id: str):
        """Remove connection and cancel associated tasks."""
        if client_id in self.connections:
            self.connections.pop(client_id, None)
            logger.info(f"Removed connection for client {client_id}. Total connections: {len(self.connections)}")

        if client_id in self.active_tasks:
            tasks_to_cancel = self.active_tasks.pop(client_id)
            for task in tasks_to_cancel: # Iterates through (receiver_task, sender_task)
                if not task.done():
                    logger.debug(f"Cancelling cleanup task {task.get_name()} for {client_id}")
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
                    except Exception as e:
                        logger.error(f"Error during cleanup task cancellation for {client_id}: {e}", exc_info=True)
        
        try:
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.close()
                logger.info(f"Closed WebSocket for client {client_id}.")
        except RuntimeError as e:
            logger.warning(f"Error closing WebSocket for client {client_id} (might be already closed): {e}")
        except Exception as e:
            logger.error(f"Unexpected error during WebSocket close for client {client_id}: {e}", exc_info=True)
            
    async def _outgoing_messages_loop(self, client_id: str):
        """
        Dequeues messages from the websocket_out_queue and sends them to the
        appropriate client. This loop specifically handles messages that have
        'destination': 'frontend' and a matching 'client_id'.
        """
        logger.info(f"Starting outgoing message loop for client {client_id}.")
        try:
            while self._running:
                # We need to peek/filter the queue if it's a shared queue,
                # or ensure the MessageRouter only puts client-specific messages here.
                # Assuming 'websocket_out_queue' is a general queue for all outgoing WS messages,
                # we must dequeue and check the client_id. If it's not for this client,
                # we re-enqueue it (less efficient but ensures messages aren't lost).
                # A more efficient design would involve client-specific outgoing queues.

                # For simplicity and to fit the current `queues.websocket_out` design:
                # We'll dequeue, if it's for *this* client_id, we send it.
                # If not, we put it back. This assumes relatively low contention for client-specific messages.
                
                message: Optional[UniversalMessage] = None
                try:
                    # Dequeue with a timeout to allow graceful shutdown
                    message = await asyncio.wait_for(self.websocket_out_queue.dequeue(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue # Check self._running and loop again

                if message is None:
                    continue # No message, loop again

                # Filter messages based on client_id and destination
                if message.destination == "frontend" and message.client_id == client_id:
                    websocket = self.connections.get(client_id)
                    if websocket and websocket.client_state == WebSocketState.CONNECTED:
                        try:
                            # Convert UniversalMessage to JSON for sending
                            json_data = message.model_dump_json()
                            await websocket.send_text(json_data)
                            logger.debug(f"[{client_id}] Sent message (ID: {message.id}, Type: {message.type}) to frontend.")
                            # Update message's processing path after sending
                            message.processing_path.append(
                                ProcessingPathEntry(
                                    processor="WebSocketManager",
                                    status="message_sent_to_frontend",
                                    details={"websocket_status": "sent"}
                                )
                            )
                        except RuntimeError as e:
                            logger.warning(f"[{client_id}] RuntimeError sending message {message.id}: {e}. Client likely disconnected.", exc_info=True)
                            await self._send_to_dead_letter_queue(
                                message,
                                reason="RuntimeError during WS send",
                                client_id=client_id,
                                error_type="WebSocketSendError",
                                error_details=str(e)
                            )
                            # Break the loop for this client, as connection seems dead
                            break
                        except Exception as e:
                            logger.error(f"[{client_id}] Failed to send message {message.id} to frontend: {e}", exc_info=True)
                            await self._send_to_dead_letter_queue(
                                message,
                                reason="Unknown error during WS send",
                                client_id=client_id,
                                error_type="WebSocketSendError",
                                error_details=str(e)
                            )
                    else:
                        logger.warning(f"[{client_id}] WebSocket connection not found or not active for sending message {message.id}. Sending to DLQ.")
                        await self._send_to_dead_letter_queue(
                            message,
                            reason="No active WS connection for client",
                            client_id=client_id,
                            error_type="NoActiveConnection"
                        )
                else:
                    # Message not for this client or destination. Re-enqueue it if it's meant for websocket_out_queue.
                    # This implies websocket_out_queue is a common pool.
                    logger.debug(f"[{client_id}] Message {message.id} (Dest: {message.destination}, Client: {message.client_id}) not for this sender. Re-enqueuing.")
                    await self.websocket_out_queue.enqueue(message) # Put it back for another sender to pick up

        except asyncio.CancelledError:
            logger.info(f"[{client_id}] Outgoing message loop was cancelled normally.")
        except Exception as e:
            logger.critical(f"[{client_id}] CRITICAL: Outgoing message loop crashed unexpectedly: {e}", exc_info=True)
            raise
        finally:
            logger.info(f"[{client_id}] Outgoing message loop finished.")
            
    async def _receiver(self, websocket: WebSocket, client_id: str):
        """Receive messages with detailed tracing and robust error handling.
        Enqueues UniversalMessage into the incoming queue.
        """
        msg_counter = 0
        logger.info(f"Starting receiver for client {client_id}")
        
        try:
            while websocket.client_state == WebSocketState.CONNECTED and self._running:
                data = None
                try:
                    logger.debug(f"[{client_id}] [Receiver {msg_counter}] Waiting for message...")
                    data = await websocket.receive_text()
                    logger.debug(f"[{client_id}] [Receiver {msg_counter}] Received raw data: {data[:200]}...")
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
                        logger.debug(f"[{client_id}] [Receiver {msg_counter}] Parsed JSON: {json.dumps(raw_message_dict, indent=2)[:500]}...")

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

                        logger.debug(f"[{client_id}] Validated UniversalMessage (ID: {universal_message.id}, Type: {universal_message.type}) from client. Enqueuing.")

                    except json.JSONDecodeError as e:
                        logger.error(f"[{client_id}] [Receiver {msg_counter}] Invalid JSON received: {e}\nRaw data: {data[:200]}...", exc_info=True)
                        await self._send_to_dead_letter_queue(
                            original_message={"raw_data": data, "client_id": client_id},
                            reason="JSON decode error",
                            client_id=client_id,
                            error_type="JSONDecodeError",
                            error_details=str(e)
                        )
                        continue 
                    except ValidationError as e:
                        logger.error(f"[{client_id}] [Receiver {msg_counter}] Pydantic validation error for incoming message (UniversalMessage schema): {e.errors()}\nRaw dict: {raw_message_dict}", exc_info=True)
                        await self._send_to_dead_letter_queue(
                            original_message=raw_message_dict,
                            reason="Pydantic validation error",
                            client_id=client_id,
                            error_type="PydanticValidationError_UniversalMessage",
                            error_details=str(e)
                        )
                        continue 
                    except Exception as e:
                        logger.critical(f"[{client_id}] [Receiver {msg_counter}] CRITICAL: Unexpected error during message parsing/validation: {e}\nRaw data: {data[:200]}...", exc_info=True)
                        await self._send_to_dead_letter_queue(
                            original_message={"raw_data": data, "client_id": client_id},
                            reason="Receiver parsing error",
                            client_id=client_id,
                            error_type="ReceiverParsingError",
                            error_details=str(e)
                        )
                        continue

                    try:
                        logger.debug(f"[{client_id}] [Receiver {msg_counter}] Enqueueing message {universal_message.id} of type '{universal_message.type}' to incoming_queue.")
                        await self.incoming_queue.enqueue(universal_message)
                    except Exception as e:
                        logger.error(f"[{client_id}] [Receiver {msg_counter}] Failed to enqueue message {universal_message.id} to incoming_queue: {e}", exc_info=True)
                        await self._send_to_dead_letter_queue(
                            original_message=universal_message,
                            reason="Queue enqueue error",
                            client_id=client_id,
                            error_type="QueueEnqueueError",
                            error_details=str(e)
                        )
                        await asyncio.sleep(0.1)

        except asyncio.CancelledError:
            logger.info(f"[{client_id}] Receiver task was cancelled normally.")
        except Exception as e:
            logger.critical(f"[{client_id}] CRITICAL: Receiver task crashed unexpectedly: {e}", exc_info=True)
            raise 
        finally:
            logger.info(f"[{client_id}] Receiver task finished.")

    async def shutdown(self):
        """Gracefully shuts down the WebSocket manager and closes all connections."""
        logger.info("Initiating WebSocketManager shutdown...")
        self._running = False

        # Cancel all active tasks (receiver and sender for each client)
        for client_id, tasks in list(self.active_tasks.items()):
            logger.info(f"Cancelling all tasks for client {client_id}.")
            for task in tasks:
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except Exception as e:
                        logger.warning(f"Error during task cancellation for client {client_id}: {e}")

        for client_id, websocket in list(self.connections.items()):
            logger.info(f"Closing WebSocket for client {client_id}.")
            try:
                if websocket.client_state == WebSocketState.CONNECTED:
                    await websocket.close()
            except Exception as e:
                logger.warning(f"Error closing WebSocket for client {client_id}: {e}")
        
        self.connections.clear()
        self.active_tasks.clear()
        logger.info("WebSocketManager shutdown complete.")