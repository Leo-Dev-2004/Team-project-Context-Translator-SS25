# backend/src/modules/MessageProcessor.py

import asyncio
import copy
import logging
import time
import uuid
from typing import Optional, Dict, Any, Union, cast
from pydantic import ValidationError

# Import all necessary Pydantic models for type hinting and instantiation
# Ensure correct imports based on your message_types.py
from ..models.message_types import (
    ProcessingPathEntry, # For processing_path
    ForwardingPathEntry, # For forwarding_path
    WebSocketMessage,
    ErrorTypes, # Assuming this is an Enum
    QueueMessage,
    DeadLetterMessage,
    SystemMessage # Imported for clarity, but logic will treat it carefully
)

from .Queues import queues # Assuming this provides MessageQueue instances

logger = logging.getLogger(__name__)

class MessageProcessor:
    def __init__(self):
        self._running = False
        self._processing_task: Optional[asyncio.Task] = None
        self._input_queue: Optional[Any] = None # Will be MessageQueue[QueueMessage]
        self._output_queue: Optional[Any] = None # Will be MessageQueue[QueueMessage]
        self._dead_letter_queue: Optional[Any] = None # Will be MessageQueue[DeadLetterMessage]

    async def initialize(self):
        """Sichere Initialisierung mit Queue-Validierung"""
        try:
            self._input_queue = queues.from_frontend
            self._output_queue = queues.to_frontend
            self._dead_letter_queue = queues.dead_letter

            if None in (self._input_queue, self._output_queue, self._dead_letter_queue):
                raise RuntimeError("One or more MessageProcessor queues not initialized correctly")

            logger.info("MessageProcessor queues verified and initialized.")
        except Exception as e:
            logger.error(f"Failed to initialize MessageProcessor: {str(e)}", exc_info=True)
            raise

    def _get_input_queue_size(self) -> int:
        """Returns the size of the input queue."""
        if self._input_queue:
            return self._input_queue.qsize()
        return 0

    async def start(self):
        """Starts the main message processing loop as a background task."""
        if not self._running:
            self._running = True
            logger.info("Starting MessageProcessor task.")
            self._processing_task = asyncio.create_task(self._process_messages())
            self._dlq_monitor_task = asyncio.create_task(self.monitor_dead_letter_queue_task())
            logger.info("MessageProcessor and Dead Letter Queue monitor tasks created and running in background.")
        else:
            logger.info("MessageProcessor already running.")

    async def _process_messages(self):
        """Main processing loop with robust error handling"""
        logger.info("MessageProcessor main loop started.")

        processed_count = 0
        last_log_time = time.time()

        while self._running:
            # We expect QueueMessage from the input queue
            message: Optional[QueueMessage] = None
            try:
                if self._input_queue is None or self._output_queue is None or self._dead_letter_queue is None:
                    logger.error("MessageProcessor queues are not initialized. Cannot process messages.")
                    await asyncio.sleep(1)
                    continue

                try:
                    message = await asyncio.wait_for(self._input_queue.dequeue(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue  # Check if still running and loop again
                if message is None:
                    await asyncio.sleep(0.1) # Short sleep to prevent busy-wait
                    continue

                # Add a processing path entry for MessageProcessor's entry point
                if message.processing_path is None: # Pydantic default_factory should prevent None
                    message.processing_path = []
                message.processing_path.append(
                    ProcessingPathEntry(
                        processor="MessageProcessor",
                        status="dequeued_for_processing",
                        details={"from_queue": "from_frontend"} # `details` is a dict for ProcessingPathEntry
                    )
                )
                logger.debug(f"MessageProcessor dequeued message {message.id} of type '{message.type}'. Client ID: {message.client_id}.")

                await self._process_single_message(message)

                processed_count += 1

                if time.time() - last_log_time > 5:
                    logger.info(f"Processed {processed_count} messages in the last 5 seconds. Input Queue Size: {self._get_input_queue_size()}")
                    last_log_time = time.time()
                    processed_count = 0

            except asyncio.CancelledError:
                logger.info("MessageProcessor task was cancelled gracefully.")
                break
            except Exception as e:
                logger.error(f"Error during MessageProcessor main loop: {str(e)}", exc_info=True)
                dlq_client_id = getattr(message, 'client_id', 'unknown_client_error') if message else 'unknown_client_error'
                original_msg_data = message.model_dump() if message and hasattr(message, 'model_dump') else {"raw_message": str(message)}
                await self._dead_letter_queue.enqueue(DeadLetterMessage(
                    original_message=original_msg_data,
                    error_details={"exception": str(e), "component": "MessageProcessor._process_messages_loop"}, # Using error_details as a dict
                    # --- FIX: Use .value for Enum member ---
                    reason=ErrorTypes.INTERNAL.value, # Use a generic internal error for loop exceptions
                    client_id=dlq_client_id,
                    # DeadLetterMessage inherits from QueueMessage, so 'type' and 'id' are handled in its __init__
                ))
                await asyncio.sleep(1)

        logger.info("MessageProcessor main loop stopped.")

    async def monitor_dead_letter_queue_task(self):
        """
        Background task to monitor the dead_letter_queue for unprocessable messages.
        """
        logger.info("Starting Dead Letter Queue monitor task.")
        if self._dead_letter_queue is None:
            logger.error("Dead Letter Queue is not initialized. Cannot monitor.")
            return

        while self._running:
            try:
                # Expect DeadLetterMessage from this queue
                message: Optional[DeadLetterMessage] = await self._dead_letter_queue.dequeue()
                
                if message:
                    logger.critical(
                        f"Dead Letter Queue received message: {getattr(message, 'id', 'N/A')} "
                        f"of type {getattr(message, 'type', 'N/A')}. "
                        f"Reason: {message.reason}. "
                        # --- FIX: Access error_details dictionary and log its content ---
                        f"Error Details: {message.error_details}. "
                        f"Original Message: {message.original_message}"
                    )
                else:
                    logger.debug("Queue 'dead_letter' empty, waiting to dequeue...")
                await asyncio.sleep(0.5)
            except asyncio.CancelledError:
                logger.info("Dead Letter Queue monitor task cancelled.")
                break
            except Exception as e:
                logger.error(f"Error in Dead Letter Queue monitor task: {e}", exc_info=True)
                await asyncio.sleep(5)
        logger.info("Dead Letter Queue monitor task stopped.")

    async def _process_single_message(self, message: QueueMessage) -> None:
        """
        Processes a single QueueMessage. This function expects `QueueMessage` instances,
        and its primary responsibility is to extract and handle the contained `WebSocketMessage`
        from `message.data`.
        """
        msg: Optional[WebSocketMessage] = None
        msg_id: str = message.id if message.id else "unknown"
        client_id: Optional[str] = message.client_id

        try:
            # We expect `QueueMessage.data` to contain a `WebSocketMessage` or be a dict for it.
            if isinstance(message.data, WebSocketMessage):
                msg = message.data
            elif isinstance(message.data, dict):
                msg = WebSocketMessage.model_validate(message.data)
            else:
                # If message.data is not a WebSocketMessage or dict, it's an unexpected format for this processor
                raise TypeError(f"Unexpected data format in QueueMessage.data (ID: {msg_id}): {type(message.data).__name__}. Expected WebSocketMessage or dict.")

            if msg is None: # Should not happen if WebSocketMessage.model_validate succeeds or raises
                raise ValueError(f"Failed to extract WebSocketMessage from QueueMessage (ID: {msg_id}).")

            # Update client_id from the extracted WebSocketMessage if available
            if msg.client_id:
                client_id = msg.client_id

            logger.info(f"Processing WebSocket message ID: {msg_id}, Type: {msg.type}, Client ID: {client_id}")

            # Add a processing path entry for this specific message type handler
            message.processing_path.append(
                ProcessingPathEntry(
                    processor="MessageProcessor",
                    status=f"handling_{msg.type}",
                    details={"message_type_handled": msg.type} # `details` is a dict
                )
            )

            # Add a forwarding path entry if this message came from a queue
            if message.from_queue:
                message.forwarding_path.append(
                    ForwardingPathEntry(
                        processor="MessageProcessor",
                        status="dequeued_from_source",
                        from_queue=message.from_queue
                    )
                )

            # --- Handle specific WebSocketMessage types ---
            if msg.type == "frontend_ready_ack":
                logger.info(f"Received 'frontend_ready_ack' from client {client_id}. Frontend is ready.")
                # Create a response wrapped in QueueMessage to send back to frontend
                response_message = QueueMessage(
                    id=f"backend-ready-confirm-{msg.id}",
                    type="backend_ready_confirm",
                    data={"message": "Backend received your ready signal!", "timestamp": time.time()},
                    client_id=client_id,
                    forwarding_path=copy.deepcopy(message.forwarding_path), # Propagate path
                    processing_path=copy.deepcopy(message.processing_path) # Propagate path
                )
                await self._output_queue.enqueue(response_message)
                logger.info(f"Enqueued backend_ready_confirm for client {client_id}.")

            elif msg.type == "ping":
                logger.debug(f"Received 'ping' from client {client_id}. Sending 'pong'.")
                # Create a pong response wrapped in QueueMessage
                pong_response = QueueMessage(
                    id=f"pong-{msg.id}",
                    type="pong",
                    data={"timestamp": time.time()},
                    client_id=client_id,
                    forwarding_path=copy.deepcopy(message.forwarding_path),
                    processing_path=copy.deepcopy(message.processing_path)
                )
                await self._output_queue.enqueue(pong_response)
                logger.debug(f"Enqueued pong response for client {client_id}.")

            elif msg.type == "user_input":
                logger.info(f"Received user input from {client_id}: {msg.data.get('text')}")
                # This message might need to be forwarded to another internal backend queue
                # for actual processing (e.g., a language model, context manager).
                # Example: If you have a 'to_backend_logic' queue:
                # await self.safe_enqueue(queues.to_backend_logic, message)
                
                # Add path entry indicating where it's being forwarded to
                message.forwarding_path.append(
                    ForwardingPathEntry(
                        processor="MessageProcessor",
                        status="forwarding_user_input",
                        to_queue="to_backend_logic_queue_example" # Placeholder
                    )
                )
                logger.info(f"User input from {client_id} processed by MessageProcessor for forwarding.")

            elif msg.type == "start_simulation":
                logger.info(f"Starting simulation for client {client_id} with data: {msg.data}")
                # This command would typically go to a Simulation Manager
                # await self.safe_enqueue(queues.simulation_commands, message)
                message.forwarding_path.append(
                    ForwardingPathEntry(
                        processor="MessageProcessor",
                        status="forwarding_to_simulation_manager",
                        to_queue="to_simulation_manager_queue_example" # Placeholder
                    )
                )
                logger.info(f"Simulation start command for {client_id} processed by MessageProcessor for forwarding.")

            elif msg.type == "frontend_init":
                logger.info(f"Frontend initialized by client {client_id} with message: {msg.data.get('message')}")
                message.processing_path.append(
                    ProcessingPathEntry(
                        processor="MessageProcessor",
                        status="frontend_init_acknowledged"
                    )
                )
                # No immediate response needed unless specific init data is expected by frontend.
            
            elif msg.type == "system_message":
                # If a WebSocketMessage of type "system_message" is received, handle it.
                # This assumes your frontend sends system messages directly.
                logger.info(f"Received system message from client {client_id}: {msg.data.get('text')}")
                message.processing_path.append(
                    ProcessingPathEntry(
                        processor="MessageProcessor",
                        status="system_message_processed"
                    )
                )

            else:
                logger.warning(f"Unknown WebSocket message type: {msg.type} from client {client_id}. Sending to DLQ.")
                await self.safe_enqueue(self._dead_letter_queue, DeadLetterMessage(
                    original_message=message.model_dump(), # original_message is the QueueMessage that contained the WS message
                    # --- FIX: Use .value for Enum member ---
                    reason=ErrorTypes.UNKNOWN_MESSAGE_TYPE.value,
                    error_details={
                        "type": "UnknownWebSocketMessageType",
                        "message": f"No specific handler found for WebSocket message type: {msg.type}",
                        "component": "MessageProcessor._process_single_message",
                        "timestamp": time.time(),
                        "client_id": client_id,
                        "original_websocket_message_id": msg.id
                    },
                    client_id=client_id, # Ensure client_id is passed to DeadLetterMessage init
                ))
            
            # Final path entry for successful processing
            message.processing_path.append(
                ProcessingPathEntry(
                    processor="MessageProcessor",
                    status="processing_complete",
                    details={"handled_type": msg.type}
                )
            )

        except ValidationError as e:
            logger.error(f"Validation error during single message processing for message {msg_id}: {e}")
            dlq_client_id = client_id or 'unknown_client_error'
            await self.safe_enqueue(self._dead_letter_queue, DeadLetterMessage(
                original_message=message.model_dump(),
                # --- FIX: Use .value for Enum member ---
                reason=ErrorTypes.VALIDATION.value, # Use 'VALIDATION' for validation errors
                error_details={"validation_error": str(e), "component": "MessageProcessor._process_single_message"},
                client_id=dlq_client_id,
            ))
        except TypeError as e:
            logger.error(f"Type error during single message processing for message {msg_id}: {e}", exc_info=True)
            dlq_client_id = client_id or 'unknown_client_error'
            await self.safe_enqueue(self._dead_letter_queue, DeadLetterMessage(
                original_message=message.model_dump(),
                # --- FIX: Use .value for Enum member ---
                reason=ErrorTypes.INTERNAL.value, # Generic internal error for type issues
                error_details={"type_error": str(e), "component": "MessageProcessor._process_single_message"},
                client_id=dlq_client_id,
            ))
        except ValueError as e:
            logger.error(f"Value error during single message processing for message {msg_id}: {e}", exc_info=True)
            dlq_client_id = client_id or 'unknown_client_error'
            await self.safe_enqueue(self._dead_letter_queue, DeadLetterMessage(
                original_message=message.model_dump(),
                # --- FIX: Use .value for Enum member ---
                reason=ErrorTypes.INTERNAL.value, # Generic internal error for value issues
                error_details={"value_error": str(e), "component": "MessageProcessor._process_single_message"},
                client_id=dlq_client_id,
            ))
        except Exception as e:
            logger.error(f"Critical error during single message processing for message {msg_id}: {str(e)}", exc_info=True)
            dlq_client_id = client_id or 'unknown_client_error'
            await self.safe_enqueue(self._dead_letter_queue, DeadLetterMessage(
                original_message=message.model_dump(),
                # --- FIX: Use .value for Enum member ---
                reason=ErrorTypes.INTERNAL.value, # Generic internal error for unexpected exceptions
                error_details={"exception": str(e), "component": "MessageProcessor._process_single_message"},
                client_id=dlq_client_id,
            ))

    # --- Removed _safe_dequeue as it wasn't used and dequeue() handles errors implicitly ---

    async def safe_enqueue(self, queue, message: Union[QueueMessage, DeadLetterMessage]) -> bool:
        """Thread-safe enqueue with error handling, ensuring type safety."""
        try:
            if queue:
                # Ensure the message is of a type compatible with the queue
                if not isinstance(message, (QueueMessage, DeadLetterMessage)):
                    # This check is crucial to prevent type issues with the queue
                    logger.error(f"Attempted to enqueue unsupported message type to queue: {type(message).__name__}. Message: {message}")
                    return False
                
                await queue.enqueue(message)
                return True
            logger.warning("Attempted to enqueue to an uninitialized queue.")
            return False
        except Exception as e:
            logger.error(f"Safe Enqueue failed in MessageProcessor for message ID {getattr(message, 'id', 'N/A')}: {str(e)}", exc_info=True)
            return False

    async def stop(self):
        """Graceful shutdown for the MessageProcessor."""
        if self._running:
            self._running = False
            logger.debug("MessageProcessor shutdown initiated. Waiting for tasks to complete...")
            if self._processing_task:
                self._processing_task.cancel()
                try:
                    await self._processing_task
                except asyncio.CancelledError:
                    pass
            if hasattr(self, '_dlq_monitor_task') and self._dlq_monitor_task:
                self._dlq_monitor_task.cancel()
                try:
                    await self._dlq_monitor_task
                except asyncio.CancelledError:
                    pass
            logger.info("MessageProcessor shutdown complete.")
        else:
            logger.info("MessageProcessor was not running.")
