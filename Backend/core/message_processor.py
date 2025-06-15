# backend/src/modules/MessageProcessor.py

import asyncio
import copy
import logging
import time
import uuid
from typing import Optional, Dict, Any, Union, cast # Import Union for type hints
from pydantic import ValidationError

# Import all necessary Pydantic models for type hinting and instantiation
from ..models.message_types import ProcessingPathEntry, WebSocketMessage, ErrorTypes, QueueMessage, DeadLetterMessage

from .Queues import queues

logger = logging.getLogger(__name__)

class MessageProcessor:
    def __init__(self):
        self._running = False
        self._processing_task: Optional[asyncio.Task] = None
        # Type hints to clarify that these will be MessageQueue instances
        self._input_queue: Optional[Any] = None # Will be MessageQueue
        self._output_queue: Optional[Any] = None # Will be MessageQueue
        self._dead_letter_queue: Optional[Any] = None # Will be MessageQueue

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
            return self._input_queue.qsize() # Use qsize()
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
            # Declare message with a Union type as it could be various Pydantic models
            message: Optional[Union[QueueMessage, DeadLetterMessage, WebSocketMessage]] = None
            try:
                if self._input_queue is None or self._output_queue is None or self._dead_letter_queue is None:
                    logger.error("MessageProcessor queues are not initialized. Cannot process messages.")
                    await asyncio.sleep(1)
                    continue

                message = await self._input_queue.dequeue()
                # Use getattr for consistent access to Pydantic model attributes
                logger.debug(f"MessageProcessor dequeued message {getattr(message, 'id', 'N/A')} of type '{getattr(message, 'type', 'N/A')}'.")

                if message is None:
                    await asyncio.sleep(0.1)
                    continue

                await self._process_single_message(message)

                processed_count += 1

                if time.time() - last_log_time > 5:
                    logger.info(f"Processed {processed_count} messages in the last 5 seconds.")
                    last_log_time = time.time()
                    processed_count = 0

            except asyncio.CancelledError:
                logger.info("MessageProcessor task was cancelled gracefully.")
                break
            except Exception as e:
                logger.error(f"Error during MessageProcessor main loop: {str(e)}", exc_info=True)
                # Directly use the 'message' variable (which is a Pydantic model)
                dlq_client_id = getattr(message, 'client_id', 'unknown_client_error') if message else 'unknown_client_error'
                await self.safe_enqueue(self._dead_letter_queue, DeadLetterMessage( # Instantiate DeadLetterMessage
                    original_message=message.model_dump() if message and hasattr(message, 'model_dump') else {"raw_message": str(message)}, # Ensure it's always a dict
                    error='processing_exception',
                    details=str(e),
                    timestamp=time.time(),
                    client_id=dlq_client_id,
                    reason='processing_error'
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
                message = await self._dead_letter_queue.dequeue()
                
                if message:
                    # Use getattr for consistent access to Pydantic model attributes
                    logger.warning(f"Dead Letter Queue received message: {getattr(message, 'id', 'N/A')} of type {getattr(message, 'type', 'N/A')}. Content: {message}")
                else:
                    logger.debug("Queue 'dead_letter' empty, waiting to dequeue...")

            except asyncio.CancelledError:
                logger.info("Dead Letter Queue monitor task cancelled.")
                break
            except Exception as e:
                logger.error(f"Error in Dead Letter Queue monitor task: {e}", exc_info=True)
                await asyncio.sleep(5)
        logger.info("Dead Letter Queue monitor task stopped.")

   
    async def _process_single_message(self, message: Union[QueueMessage, WebSocketMessage]) -> None:
        """
        Processes a single message from the queue, dispatching it based on its type.
        This function handles messages that are either direct WebSocketMessages
        or QueueMessages that contain a WebSocketMessage in their 'data' field.
        """
        msg: Optional[WebSocketMessage] = None
        msg_id: str = "unknown"

        try:
            if isinstance(message, QueueMessage):
                if isinstance(message.data, WebSocketMessage):
                    msg = message.data
                elif isinstance(message.data, dict):
                    msg = WebSocketMessage.model_validate(message.data)
                else:
                    raise TypeError(f"Unexpected type in QueueMessage.data: {type(message.data).__name__}. Expected WebSocketMessage or dict.")
            elif isinstance(message, WebSocketMessage):
                msg = message
            else:
                raise TypeError(f"Received unsupported message type for processing: {type(message).__name__}. Expected QueueMessage or WebSocketMessage.")

            msg_id = msg.id if msg.id is not None else "unknown"

            logger.info(f"Processing message ID: {msg_id}, Type: {msg.type}, Client ID: {msg.client_id}")

            # --- MODIFIED: Add handlers for 'frontend_ready_ack' and 'ping' ---
            if msg.type == "frontend_ready_ack":
                logger.info(f"Received 'frontend_ready_ack' from client {msg.client_id}. Frontend is ready.")
                # Optional: Send a confirmation back to the frontend
                await self.safe_enqueue(self._output_queue, QueueMessage(
                    id=f"backend-ready-confirm-{msg.id}",
                    type="backend_ready_confirm", # You'll need to define this type in WebSocketMessage if you send it
                    data={"message": "Backend received your ready signal!"},
                    client_id=msg.client_id
                ))
            elif msg.type == "ping":
                logger.debug(f"Received 'ping' from client {msg.client_id}. Sending 'pong'.")
                await self.safe_enqueue(self._output_queue, QueueMessage(
                    id=f"pong-{msg.id}",
                    type="pong", # Frontend should expect a 'pong' type message
                    data={"timestamp": time.time()},
                    client_id=msg.client_id
                ))
            elif msg.type == "user_input":
                logger.info(f"Received user input from {msg.client_id}: {msg.data.get('text')}")
                # Process user input as before
            elif msg.type == "start_simulation":
                logger.info(f"Starting simulation for client {msg.client_id}")
                # Start simulation as before
            elif msg.type == "frontend_init": # Assuming frontend_init is distinct from frontend_ready_ack
                logger.info(f"Frontend initialized by client {msg.client_id} with message: {msg.data.get('message')}")
            else:
                logger.warning(f"Unknown WebSocket message type: {msg.type} from client {msg.client_id}. Sending to DLQ.")
                await self.safe_enqueue(self._dead_letter_queue, DeadLetterMessage(
                    original_message=msg.model_dump(),
                    reason="UnknownMessageType",
                    error_details={
                        "type": "UnknownMessageType",
                        "message": f"No handler found for type: {msg.type}",
                        "component": "MessageProcessor",
                        "timestamp": time.time(),
                        "client_id": msg.client_id
                    },
                    client_id=msg.client_id,
                    id=f"dlq-{msg.id}"
                ))

        except ValidationError as e:
            # This catches validation errors during initial message parsing or within command logic
            logger.error(f"Validation error during single message processing for message {msg_id}: {e}")
            dlq_client_id = getattr(msg, 'client_id', 'unknown_client_error') if 'msg' in locals() else 'unknown_client_error'
            await self.safe_enqueue(self._dead_letter_queue, DeadLetterMessage(
                original_message=msg.model_dump() if msg is not None and hasattr(msg, 'model_dump') else (message.model_dump() if hasattr(message, 'model_dump') else {"raw_message": str(message)}),
                error='message_validation_failed',
                details=str(e),
                timestamp=time.time(),
                client_id=dlq_client_id,
                reason='validation_failed_during_single_message_processing'
            ))
        except Exception as e:
            # This catches any other unexpected errors during single message processing
            logger.error(f"Critical error during single message processing for message {msg_id}: {str(e)}", exc_info=True)
            dlq_client_id = getattr(msg, 'client_id', 'unknown_client_error') if 'msg' in locals() else 'unknown_client_error'
            await self.safe_enqueue(self._dead_letter_queue, DeadLetterMessage(
                original_message=msg.model_dump() if msg is not None and 'msg' in locals() and hasattr(msg, 'model_dump') else (message.model_dump() if hasattr(message, 'model_dump') else {"raw_message": str(message)}),
                error='message_processing_exception',
                details=str(e),
                timestamp=time.time(),
                client_id=dlq_client_id,
                reason='critical_error_during_single_message_processing'
            ))


    async def _safe_dequeue(self, queue) -> Optional[Union[QueueMessage, DeadLetterMessage, WebSocketMessage]]:
        """Thread-safe dequeue with error handling."""
        try:
            return await queue.dequeue() if queue else None
        except Exception as e:
            logger.warning(f"Safe Dequeue failed in MessageProcessor: {str(e)}")
            return None

    async def safe_enqueue(self, queue, message: Union[QueueMessage, DeadLetterMessage, WebSocketMessage]) -> bool:
        """Thread-safe enqueue with error handling."""
        try:
            if queue:
                await queue.enqueue(message)
                return True
            return False
        except Exception as e:
            logger.warning(f"Safe Enqueue failed in MessageProcessor: {str(e)}")
            return False

    async def stop(self):
        """Graceful shutdown for the MessageProcessor."""
        if self._running:
            self._running = False
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
