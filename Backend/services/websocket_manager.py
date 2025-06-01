import asyncio
import json
import logging
import time
import uuid
from uuid import uuid4
from pydantic import ValidationError, BaseModel # Import BaseModel if you use it for custom models
from fastapi import WebSocket
from fastapi.websockets import WebSocketState
from typing import Dict, Any, Optional, Union
from starlette.websockets import WebSocketDisconnect

# Ensure these imports match your actual queue and model paths
from ..queues.shared_queue import get_to_frontend_queue, get_from_frontend_queue, get_dead_letter_queue
# IMPORTANT: Import QueueMessage and DeadLetterMessage from your models
from Backend.models.message_types import QueueMessage, DeadLetterMessage, WebSocketMessage # Assuming WebSocketMessage is also a Pydantic model

logger = logging.getLogger(__name__)

class WebSocketManager:
    def __init__(self, from_frontend_queue=None):
        self.connections: Dict[str, WebSocket] = {} # Store connections by client_id for easier lookup
        self.ack_status = {} # This might need re-evaluation based on new message types
        # Using a dictionary to map client_id to its tasks (sender_task, receiver_task)
        self.active_tasks: Dict[str, tuple[asyncio.Task, asyncio.Task]] = {}
        self._running = True  # Flag for graceful shutdown
        self.from_frontend_queue = from_frontend_queue if from_frontend_queue else get_from_frontend_queue()
        self.to_frontend_queue = get_to_frontend_queue()
        self.dead_letter_queue = get_dead_letter_queue()

    # Helper to get the formatted client address string
    def _get_formatted_client_address(self, websocket: WebSocket) -> str:
        client = websocket.client
        if client and hasattr(client, 'host') and hasattr(client, 'port'):
            return f"{client.host}:{client.port}"
        return "unknown"

    # _create_queue_message is likely no longer needed if we are directly using QueueMessage/DeadLetterMessage
    # from the moment we receive data from the websocket up to enqueuing.
    # If there's still a need for a generic internal message format, consider making it a Pydantic model too.
    # For now, I'll remove it, assuming QueueMessage is the standard.
    # If you need to convert a raw dict to QueueMessage, do QueueMessage(**raw_dict).

    async def _send_to_dead_letter_queue(self, original_message: Union[dict, QueueMessage, WebSocketMessage], 
                                       reason: str, client_id: str, error_type: Optional[str] = None,
                                       error_details: Optional[Union[str, Dict[str, Any]]] = None):
        """Helper to send messages to the Dead Letter Queue."""
        try:
            # Convert original_message to dict if it's a Pydantic model
            if isinstance(original_message, (QueueMessage, WebSocketMessage)):
                original_message_dict = original_message.model_dump()
            elif isinstance(original_message, dict):
                original_message_dict = original_message
            else:
                original_message_dict = {"raw_message": str(original_message)}

            # Prepare error details
            details = {
                "type": error_type or "websocket_error",
                "message": str(error_details) if isinstance(error_details, str) else reason,
                "component": "WebSocketManager",
                "timestamp": time.time(),
                "client_id": client_id
            }
            if isinstance(error_details, dict):
                details.update(error_details)

            dl_message = DeadLetterMessage(
                original_message=original_message_dict,
                reason=reason,
                error_details=details,
                client_id=client_id
            )
            await self.dead_letter_queue.enqueue(dl_message)
            logger.error(f"Message sent to DLQ (reason: {reason})")
        except Exception as e:
            logger.critical(f"Failed to send message to Dead Letter Queue: {e}\nOriginal: {original_message}", exc_info=True)


    async def handle_connection(self, websocket: WebSocket, client_id: str):
        """Handle new WebSocket connection"""
        client_info = self._get_formatted_client_address(websocket)
        
        logger.info(f"Attempting to handle connection for {client_info} (ID: {client_id})")

        try:
            await websocket.accept()
            logger.info(f"WebSocket connection accepted for {client_info} (ID: {client_id})")
            
            # Store connection by client_id instead of raw websocket object (better for lookup)
            self.connections[client_id] = websocket 
            logger.info(f"Adding connection: {client_id}. Total connections: {len(self.connections)}")

            await self.send_ack(websocket)

            # Assign names to tasks for easier debugging
            # Use client_id as key for active_tasks
            sender_task = asyncio.create_task(self._sender(websocket, client_id), name=f"sender_{client_id}")
            receiver_task = asyncio.create_task(self._receiver(websocket, client_id), name=f"receiver_{client_id}")

            self.active_tasks[client_id] = (sender_task, receiver_task)

            # Wait for either task to complete (e.g., if connection breaks)
            done, pending = await asyncio.wait(
                [sender_task, receiver_task], 
                return_when=asyncio.FIRST_COMPLETED
            )

            # If one task finishes, the other should be cancelled
            for task in pending:
                logger.info(f"Cancelling pending task {task.get_name()} for {client_id}.")
                task.cancel()
                try:
                    await task  # Await cancellation to ensure it cleans up
                except asyncio.CancelledError:
                    pass
                except Exception as e:
                    logger.error(f"Error during cancellation of {task.get_name()} for {client_id}: {e}", exc_info=True)

            # Await the completed tasks to propagate any exceptions
            for task in done:
                try:
                    await task
                except asyncio.CancelledError:
                    pass # Expected if task was cancelled
                except Exception as e:
                    logger.error(f"Exception in completed task {task.get_name()} for {client_id}: {e}", exc_info=True)
                    raise # Re-raise critical exceptions to allow FastAPI/Uvicorn to catch them

        except WebSocketDisconnect as e:
            logger.info(f"WebSocket disconnected from {client_info} (ID: {client_id}) during handle_connection: Code {e.code}, Reason: '{e.reason}'")
        except asyncio.CancelledError:
            logger.info(f"Handle connection task for {client_info} (ID: {client_id}) was cancelled.")
        except Exception as e:
            logger.critical(f"CRITICAL: Unhandled error in handle_connection for {client_info} (ID: {client_id}): {e}", exc_info=True)
            raise # Re-raise to signal a fatal error to Uvicorn
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
            sender_task, receiver_task = self.active_tasks.pop(client_id)
            for task in [sender_task, receiver_task]:
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

    async def send_ack(self, websocket: WebSocket):
        """Sends an acknowledgement message to the connected client."""
        ack_message = {
            "type": "ack",
            "data": {"message": "Connection established", "timestamp": time.time()}
        }
        try:
            await websocket.send_json(ack_message)
            logger.debug("Acknowledgement sent to client.")
        except Exception as e:
            logger.error(f"Failed to send ACK: {e}", exc_info=True)

    async def send_error(self, websocket: WebSocket, error_type: str, error_message: str):
        """Sends an error message to the connected client."""
        error_response = {
            "type": "error",
            "data": {"error_type": error_type, "message": error_message, "timestamp": time.time()}
        }
        try:
            await websocket.send_json(error_response)
            logger.debug(f"Error message '{error_type}' sent to client.")
        except Exception as e:
            logger.error(f"Failed to send error message to client: {e}", exc_info=True)


    async def _sender(self, websocket: WebSocket, client_id: str):
        """Send messages from to_frontend_queue to client"""
        logger.info(f"Sender task started for client {client_id}")
        try:
            while websocket.client_state == WebSocketState.CONNECTED and self._running:
                try:
                    # Dequeue message from the shared to_frontend_queue
                    # This now returns a Pydantic QueueMessage or DeadLetterMessage object
                    message: Union[QueueMessage, DeadLetterMessage] = await asyncio.wait_for(
                        self.to_frontend_queue.dequeue(),
                        timeout=1.0 # Short timeout to check connection status and running flag
                    )
                except asyncio.TimeoutError:
                    if not self._running: # If manager is shutting down, exit
                        logger.debug(f"[{client_id}] Sender detected manager shutdown. Exiting.")
                        break
                    continue # No message in queue, continue loop to check again

                # No need for message is None check, dequeue blocks or raises TimeoutError

                logger.debug(f"[{client_id}] Sender dequeued message {message.id} of type '{message.type}' from to_frontend_queue.")

                try:
                    # The message is already a Pydantic object (QueueMessage or DeadLetterMessage)
                    # We need to ensure it's suitable for the WebSocketMessage schema if it's different.
                    # For simplicity, let's assume QueueMessage can be directly converted to WebSocketMessage.
                    # If WebSocketMessage has a different structure, you'd map fields here.
                    
                    # Ensure client_id is set in the message for forwarding
                    if not message.client_id:
                        message.client_id = client_id # Assign current client_id if missing

                    # Convert the QueueMessage/DeadLetterMessage to WebSocketMessage if necessary
                    # Assuming WebSocketMessage can be instantiated from QueueMessage/DeadLetterMessage fields
                    ws_msg = WebSocketMessage(
                        id=message.id,
                        type=message.type,
                        data=message.data,
                        timestamp=message.timestamp,
                        client_id=message.client_id,
                        # Add any other fields WebSocketMessage expects that are in QueueMessage
                    )
                    logger.debug(f"[{client_id}] Prepared WebSocket message of type '{ws_msg.type}' for sending.")

                except ValidationError as e:
                    logger.error(f"[{client_id}] Invalid message format for sending from queue: {e.errors()}\nOriginal message: {message}", exc_info=True)
                    await self.send_error(websocket, "backend_message_validation_failed", f"Backend message invalid: {str(e.errors())}")
                    await self._send_to_dead_letter_queue(
                        original_message=message,
                        reason="Sender validation error",
                        client_id=client_id,
                        error_type="SenderValidationError",
                        error_details=str(e)
                    )
                    continue # Skip sending this malformed message
                except Exception as e:
                    logger.critical(f"[{client_id}] CRITICAL: Unexpected error preparing message in sender: {e}", exc_info=True)
                    await self._send_to_dead_letter_queue(
                        original_message=message,
                        reason="Sender prepare error", 
                        client_id=client_id,
                        error_type="SenderPrepareError",
                        error_details=str(e)
                    )
                    continue

                try:
                    if websocket.client_state == WebSocketState.CONNECTED:
                        json_data = ws_msg.model_dump_json() # Pydantic v2
                        await websocket.send_text(json_data)
                        logger.debug(f"[{client_id}] Sent message {ws_msg.id} (type: {ws_msg.type}) to client.")
                    else:
                        logger.warning(f"[{client_id}] WebSocket not connected for send, discarding message {ws_msg.id}. State: {websocket.client_state.name}")
                        break # Exit loop if connection is no longer active
                except WebSocketDisconnect:
                    logger.info(f"[{client_id}] WebSocket disconnected during send. Exiting sender.")
                    break # Exit loop on disconnection
                except RuntimeError as e:
                    # This often means the WebSocket connection is broken on the network layer
                    logger.warning(f"[{client_id}] WebSocket runtime error during send: {e}. Assuming disconnection.", exc_info=True)
                    break # Exit loop on connection error
                except Exception as e:
                    logger.error(f"[{client_id}] Unexpected error sending message {ws_msg.id}: {e}", exc_info=True)
                    await self._send_to_dead_letter_queue(
                        original_message=ws_msg,
                        reason="Sender send error",
                        client_id=client_id,
                        error_type="SenderSendError",
                        error_details=str(e)
                    )
                    await asyncio.sleep(0.1) # Small backoff on send errors to prevent flood

        except asyncio.CancelledError:
            logger.info(f"[{client_id}] Sender task was cancelled normally.")
        except Exception as e:
            logger.critical(f"[{client_id}] CRITICAL: Sender task crashed unexpectedly: {e}", exc_info=True)
            raise # Re-raise critical exceptions to signal a fatal error
        finally:
            logger.info(f"[{client_id}] Sender task finished.")

    async def _receiver(self, websocket: WebSocket, client_id: str):
        """Receive messages with detailed tracing and robust error handling"""
        msg_counter = 0

        logger.info(f"Starting receiver for client {client_id} with enhanced message tracing")
        
        try:
            while websocket.client_state == WebSocketState.CONNECTED and self._running:
                data = None # Initialize data to None for scope
                try:
                    logger.debug(f"[{client_id}] [Receiver {msg_counter}] Waiting for message...")
                    
                    data = await websocket.receive_text()
                    logger.debug(f"[{client_id}] [Receiver {msg_counter}] Received raw data: {data[:200]}...")  # Truncate long messages
                    msg_counter += 1

                except WebSocketDisconnect as e:
                    logger.info(f"[{client_id}] WebSocket cleanly disconnected: Code {e.code}, Reason: '{e.reason}'")
                    break # Exit loop on graceful disconnect
                except asyncio.CancelledError:
                    logger.info(f"[{client_id}] Receiver task cancelled.")
                    break # Exit loop if task is cancelled
                except RuntimeError as e:
                    # This often means the WebSocket connection is broken at a lower layer
                    logger.warning(f"[{client_id}] WebSocket runtime error during receive: {e}. Assuming disconnection.", exc_info=True)
                    break # Exit loop on connection error
                except Exception as recv_error:
                    # Catch any other unexpected error during the receive_text() call itself
                    logger.critical(f"[{client_id}] CRITICAL: Unexpected error receiving message: {recv_error}", exc_info=True)
                    await asyncio.sleep(0.1) # Small backoff to prevent tight error loop
                    continue # Continue trying to receive, or break if persistent error

                # --- Message Parsing and Validation ---
                if data: # Only process if data was actually received
                    raw_message_dict: Dict[str, Any] = {} # Initialize for type hinting
                    try:
                        logger.debug(f"[{client_id}] [Receiver {msg_counter}] Parsing JSON.")
                        raw_message_dict = json.loads(data)
                        logger.debug(f"[{client_id}] [Receiver {msg_counter}] Parsed JSON: {json.dumps(raw_message_dict, indent=2)[:500]}...")

                        # --- NEW CRITICAL STEP: Validate raw_message_dict as a WebSocketMessage ---
                        parsed_websocket_message = WebSocketMessage.model_validate(raw_message_dict)
                        logger.debug(f"[{client_id}] Validated Pydantic WebSocketMessage (ID: {parsed_websocket_message.id}, Type: {parsed_websocket_message.type}) from client.")


                        # Now, create the QueueMessage using the VALIDATED WebSocketMessage object
                        message_for_queue = QueueMessage(
                            id=parsed_websocket_message.id, # Get ID from the validated WebSocketMessage
                            data=parsed_websocket_message.model_dump(), # Pass as dict, not as Pydantic object
                            client_id=parsed_websocket_message.client_id, # Get client_id from validated WebSocketMessage
                            timestamp=parsed_websocket_message.timestamp, # Get timestamp from validated WebSocketMessage                        )
                            type=parsed_websocket_message.type # Get type from validated WebSocketMessage
                        )
                        # The client_id in the message should match the connection's client_id
                        # This check is now redundant if client_id is validated in WebSocketMessage,
                        # but keeping it for safety/logging if needed.
                        if message_for_queue.client_id != client_id:
                            logger.warning(f"[{client_id}] Incoming message client_id ({message_for_queue.client_id}) does not match connection ID ({client_id}). Overriding in QueueMessage.")
                            message_for_queue.client_id = client_id

                        logger.debug(f"[{client_id}] Created Pydantic QueueMessage (ID: {message_for_queue.id}, Type: {message_for_queue.data['type']}) for queue.")


                    except json.JSONDecodeError as e:
                        logger.error(f"[{client_id}] [Receiver {msg_counter}] Invalid JSON received: {e}\nRaw data: {data[:200]}...", exc_info=True)
                        await self.send_error(websocket, "invalid_json", f"Invalid JSON format: {str(e)}")
                        await self._send_to_dead_letter_queue(
                            original_message={"raw_data": data, "client_id": client_id},
                            reason="JSON decode error",
                            client_id=client_id,
                            error_type="JSONDecodeError",
                            error_details=str(e)
                        )
                        continue # Skip to next receive loop if JSON is bad
                    except ValidationError as e:
                        # THIS IS WHERE THE ERROR WILL NOW BE CAUGHT IF THE FRONTEND SENDS BAD DATA
                        logger.error(f"[{client_id}] [Receiver {msg_counter}] Pydantic validation error for incoming message (WebSocketMessage schema): {e.errors()}\nRaw dict: {raw_message_dict}", exc_info=True)
                        await self.send_error(websocket, "message_validation_failed", f"Invalid message format: {str(e.errors())}")
                        await self._send_to_dead_letter_queue(
                            original_message=raw_message_dict,
                            reason="Pydantic validation error",
                            client_id=client_id,
                            error_type="PydanticValidationError_WebSocketMessage",
                            error_details=str(e)
                        )
                        )
                        continue # Skip to next receive loop if message is malformed
                    except Exception as e:
                        logger.critical(f"[{client_id}] [Receiver {msg_counter}] CRITICAL: Unexpected error during message parsing/validation: {e}\nRaw data: {data[:200]}...", exc_info=True)
                        await self.send_error(websocket, "internal_parsing_error", f"Internal parsing error: {str(e)}")
                        await self._send_to_dead_letter_queue(
                            original_message={"raw_data": data, "client_id": client_id},
                            reason="Receiver parsing error",
                            client_id=client_id,
                            error_type="ReceiverParsingError",
                            error_details=str(e)
                        )
                        continue

                    # --- Enqueueing the Validated Pydantic Message ---
                    try:
                        logger.debug(f"[{client_id}] [Receiver {msg_counter}] Enqueueing message {message_for_queue.id} of type '{message_for_queue.data['type']}' to from_frontend_queue.")
                        await self.from_frontend_queue.enqueue(message_for_queue)
                    except Exception as e:
                        logger.error(f"[{client_id}] [Receiver {msg_counter}] Failed to enqueue message {message_for_queue.id} to from_frontend_queue: {e}", exc_info=True)
                        await self.send_error(websocket, "queue_enqueue_failed", f"Failed to process message internally.")
                        await self._send_to_dead_letter_queue(
                            original_message=message_for_queue,
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
            raise # Re-raise critical exceptions to signal a fatal error
        finally:
            logger.info(f"[{client_id}] Receiver task finished.")



    async def shutdown(self):
        """Gracefully shuts down the WebSocket manager and closes all connections."""
        logger.info("Initiating WebSocketManager shutdown...")
        self._running = False

        # Cancel all active tasks
        for client_id, (sender_task, receiver_task) in list(self.active_tasks.items()):
            logger.info(f"Cancelling tasks for client {client_id}.")
            sender_task.cancel()
            receiver_task.cancel()
            try:
                await asyncio.gather(sender_task, receiver_task, return_exceptions=True)
            except Exception as e:
                logger.warning(f"Error during task cancellation for client {client_id}: {e}")

        # Close all remaining WebSocket connections
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

    # Your _handle_command and _handle_data methods were not used in the provided
    # endpoint/receiver flow. Assuming all messages go through _receiver -> queue.
    # If these are called from an endpoint, ensure they adhere to the same client_id
    # formatting and DLQ standards.
    async def _handle_command(self, msg: WebSocketMessage):
        """Handle command messages (e.g., start/stop simulation)."""
        client_id_str: str = msg.client_id if isinstance(msg.client_id, str) else 'unknown'
        logger.info(f"Received command: {msg.data.get('command')} from {client_id_str}")
        # This logic should likely live in MessageProcessor, not WebSocketManager
        # as it represents application-level business logic.
        # For now, it just logs.
        command = msg.data.get('command')
        if command == 'start_simulation':
            logger.info(f"Processing start_simulation command for {client_id_str}")
        elif command == 'stop_simulation':
            logger.info(f"Processing stop_simulation command for {client_id_str}")
        else:
            logger.warning(f"Unknown command received: {command} from {client_id_str}")

    async def _handle_data(self, msg: WebSocketMessage):
        """Handle generic data messages. Redundant if all messages go through the queue."""
        client_id_str: str = msg.client_id if isinstance(msg.client_id, str) else 'unknown'
        logger.info(f"Handling data message from {client_id_str} (type: {msg.type}) - this method might be redundant.")
        # This message should already be enqueued by _receiver.
        # If this is called from an API endpoint, it should enqueue to from_frontend_queue.
        # queue_msg = self._create_queue_message(msg, source='frontend_data', status='processed')
        # await self.from_frontend_queue.enqueue(queue_msg)

 
 
    async def send_message_to_client(self, client_id: str, message_data: Union[dict, QueueMessage, WebSocketMessage]) -> bool:
        """Sends a message to a specific client.
        message_data can be a dict, a QueueMessage, or a WebSocketMessage.
        Returns True on successful send, False otherwise.
        """
        logger.info(f"Attempting to send message to client: {client_id}")

        try:
            # Convert message_data to WebSocketMessage
            if isinstance(message_data, QueueMessage):
                ws_msg = message_data.to_websocket_message()
            elif isinstance(message_data, dict):
                ws_msg = WebSocketMessage.model_validate(message_data)
            elif isinstance(message_data, WebSocketMessage):
                ws_msg = message_data
            else:
                error_msg = f"Invalid message_data type: {type(message_data)}"
                logger.error(error_msg)
                await self._send_to_dead_letter_queue(
                    original_message=message_data,
                    reason=error_msg,
                    client_id=client_id
                )
                return False

            # Get target websocket
            target_websocket = self.connections.get(client_id)
            if not target_websocket:
                logger.warning(f"Client {client_id} not found in active connections")
                await self._send_to_dead_letter_queue(
                    original_message=ws_msg.model_dump(),
                    reason=f"Client {client_id} not found",
                    client_id=client_id
                )
                return False

            # Send message
            if target_websocket.client_state == WebSocketState.CONNECTED:
                await target_websocket.send_text(ws_msg.model_dump_json())
                logger.info(f"Sent message to {client_id} (type: {ws_msg.type})")
                return True
            else:
                logger.warning(f"WebSocket not connected for client {client_id}")
                await self._send_to_dead_letter_queue(
                    original_message=message_data,
                    reason=f"WebSocket not connected (State: {target_websocket.client_state})",
                    client_id=client_id
                )
                return False

        except ValidationError as e:
            logger.error(f"[{client_id}] Validation error for direct message: {e.errors()}. Original data: {message_data}", exc_info=True)
            await self._send_to_dead_letter_queue(
                original_message=message_data.model_dump() if hasattr(message_data, "model_dump") else dict(message_data),
                reason=f"Validation error: {str(e)}",
                client_id=client_id
            )
            return False
        except Exception as e:
            logger.error(f"Failed to send message to {client_id}: {e}", exc_info=True)
            await self._send_to_dead_letter_queue(
                original_message=message_data,
                reason=str(e),
                client_id=client_id
            )
            return False
