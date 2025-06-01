# backend/src/modules/MessageProcessor.py

import asyncio
import copy
import logging
import time
import uuid
from typing import Optional, Dict, Any, Union, cast # Import Union for type hints
from pydantic import ValidationError

from ..queues.shared_queue import (
    get_from_frontend_queue,
    get_to_backend_queue,
    get_to_frontend_queue,
    get_dead_letter_queue
)
# Import all necessary Pydantic models for type hinting and instantiation
from ..models.message_types import ProcessingPathEntry, WebSocketMessage, ErrorTypes, QueueMessage, DeadLetterMessage

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
            self._input_queue = get_from_frontend_queue()
            self._output_queue = get_to_frontend_queue()
            self._dead_letter_queue = get_dead_letter_queue()

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

    async def _process_single_message(self, message: Union[QueueMessage, DeadLetterMessage, WebSocketMessage]) -> None:
        """Process messages with detailed tracing and response generation."""
        # Small sleep to yield control, if necessary
        await asyncio.sleep(0.01) 
        
        # 'message' is already a Pydantic model from dequeue.
        # Access attributes directly, and ensure it's a WebSocketMessage for core logic.
        
        msg_id = getattr(message, 'id', 'unknown')
        msg_type = getattr(message, 'type', 'unknown')
        client_id = getattr(message, 'client_id', 'unknown')
        
        logger.debug(f"Processing message {msg_id} (type: {msg_type}, client: {client_id})")
        
        response_message_dict: Optional[Dict[str, Any]] = None

        # Wrap the main processing logic in a single try-except block
        try:
            msg: WebSocketMessage
            if isinstance(message, WebSocketMessage):
                msg = message
            elif isinstance(message, QueueMessage) and hasattr(message, 'data') and isinstance(message.data, dict):
                # If QueueMessage is used as a wrapper for WebSocketMessage payload
                msg = WebSocketMessage.model_validate(message.payload)
            else:
                # If message is not a WebSocketMessage or a QueueMessage with a valid payload,
                # it's an unexpected type for _process_single_message.
                raise ValidationError(f"Received unexpected message type for processing: {type(message).__name__}. Expected WebSocketMessage or QueueMessage.")

            logger.debug(f"Processing {msg.type} message from {msg.client_id}")

            effective_client_id: str
            if msg.client_id is None:
                logger.warning(f"Message {msg.id} has no client_id. Using 'unknown_client'.")
                effective_client_id = "unknown_client"
            else:
                effective_client_id = msg.client_id

            msg.processing_path.append(ProcessingPathEntry(
                processor="MessageProcessor",
                timestamp=time.time(),
                status='processed',
                completed_at=time.time()
            ))

            if msg.type == 'ping':
                logger.info(f"MessageProcessor: Received ping from {effective_client_id}")
                pong_data = {
                    "timestamp": msg.data.get('timestamp', time.time())
                }
                pong_message = WebSocketMessage(
                    id=str(uuid.uuid4()),
                    type="pong",
                    data=pong_data,
                    client_id=effective_client_id,
                    processing_path=msg.processing_path,
                    forwarding_path=msg.forwarding_path
                )
                
                # Enqueue the pong response (pass Pydantic model directly)
                await self.safe_enqueue(
                    self._output_queue,
                    pong_message
                )
                logger.info(f"Enqueued pong response for ping from {effective_client_id}")
                return  # Skip further processing for ping messages

            elif msg.type == 'command':
                command_name = msg.data.get('command')
                logger.info(f"MessageProcessor: Processing command '{command_name}' from {effective_client_id}")

                response_type: str = "error"
                response_data: Dict[str, Any] = {
                    "original_command": command_name,
                    "original_id": msg.id,
                    "client_id": effective_client_id,
                    "status": "failed",
                    "error": ErrorTypes.INTERNAL,
                    "message": "An unhandled error occurred during command processing."
                }

                try:
                    from Backend.dependencies import get_simulation_manager
                    sim_manager =  get_simulation_manager(require_ready=True)

                    if command_name == 'start_simulation':
                        await sim_manager.start(client_id=effective_client_id, background_tasks=None)
                        response_data.update({
                            "status": "simulation_started",
                            "message": "Simulation successfully started",
                            "progress": 0
                        })
                        response_type = "status"

                    elif command_name == 'stop_simulation':
                        await sim_manager.stop(client_id=effective_client_id)
                        response_data.update({
                            "status": "simulation_stopped",
                            "message": "Simulation successfully stopped"
                        })
                        response_type = "status"

                    elif command_name == 'set_translation_settings':
                        mode = msg.data.get('mode')
                        context_level = msg.data.get('context_level')

                        if mode is None or context_level is None:
                            raise ValueError("Missing 'mode' or 'context_level' for set_translation_settings command.")
                        
                        await sim_manager.set_translation_settings(mode=mode, context_level=context_level, client_id=effective_client_id)
                        
                        response_data.update({
                            "status": "success",
                            "message": f"Translation settings updated: mode='{mode}', context_level={context_level}",
                            "mode": mode,
                            "context_level": context_level
                        })
                        response_type = "status"

                    else:
                        response_type = "error"
                        response_data.update({
                            "error": ErrorTypes.COMMAND_NOT_FOUND,
                            "message": f"Command not recognized: {command_name}",
                            "status": "failed"
                        })

                except ValidationError as e:
                    logger.error(f"Command validation error: {str(e)}", exc_info=True)
                    response_type = "error"
                    response_data.update({
                        "error": ErrorTypes.VALIDATION,
                        "message": "Invalid command format",
                        "details": str(e),
                        "status": "failed"
                    })
                except ValueError as e:
                    logger.error(f"Invalid settings for command '{command_name}': {str(e)}", exc_info=True)
                    response_type = "error"
                    response_data.update({
                        "error": ErrorTypes.VALIDATION,
                        "message": f"Invalid or missing data for command '{command_name}': {str(e)}",
                        "status": "failed"
                    })
                except KeyError as e:
                    logger.error(f"Missing data for command or command not found: {str(e)}", exc_info=True)
                    response_type = "error"
                    response_data.update({
                        "error": ErrorTypes.COMMAND_NOT_FOUND,
                        "message": f"Missing required data for command '{command_name}' or command not found in data: {str(e)}",
                        "status": "failed"
                    })
                except Exception as e:
                    logger.error(f"Command processing error: {str(e)}", exc_info=True)
                    response_data.update({
                        "message": f"Internal server error during command processing: {str(e)}"
                    })
                    response_type = "error"

                finally:
                    # Create response message as a Pydantic model, then dump for dict
                    response_message_dict = WebSocketMessage(
                        type=response_type,
                        data=response_data,
                        client_id=effective_client_id,
                        processing_path=msg.processing_path,
                        forwarding_path=msg.forwarding_path
                    ).model_dump()
                    logger.info(f"Generated {response_type} response for command '{command_name}'")

            elif msg.type == 'frontend_ready_ack':
                logger.info(f"MessageProcessor: Frontend ready ACK received from {effective_client_id}. Status: {msg.data.get('message')}")
                pass # No response needed for ACK

            elif msg.type == 'data':
                logger.info(f"MessageProcessor: Forwarding data message from {effective_client_id}")
                # Create data message as a Pydantic model, then dump for dict
                response_message_dict = WebSocketMessage(
                    type="data",
                    data=msg.data,
                    client_id=effective_client_id,
                    processing_path=msg.processing_path,
                    forwarding_path=msg.forwarding_path
                ).model_dump()

            else:
                logger.warning(f"MessageProcessor: Unhandled message type: '{msg.type}' from {effective_client_id}. Sending to Dead Letter Queue.")
                await self.safe_enqueue(self._dead_letter_queue, DeadLetterMessage( # Instantiate DeadLetterMessage
                    original_message=msg.model_dump(), # Original message as dict
                    error='unhandled_message_type',
                    timestamp=time.time(),
                    client_id=effective_client_id,
                    reason='unhandled_message_type'
                ))
                return # Exit processing for unhandled types

            if response_message_dict:
                # The response_message_dict is a dict, validate it into a Pydantic model for enqueue
                response_msg_instance = WebSocketMessage.model_validate(response_message_dict)
                if not await self.safe_enqueue(self._output_queue, response_msg_instance): # Pass Pydantic model
                    logger.error(f"Failed to enqueue response message (type: {response_message_dict.get('type')}) to to_frontend_queue for client {effective_client_id}. Sending to DLQ.")
                    await self.safe_enqueue(self._dead_letter_queue, DeadLetterMessage( # Instantiate DeadLetterMessage
                        original_message=response_message_dict, # Pass the dict representation
                        error='response_enqueue_failed',
                        timestamp=time.time(),
                        client_id=effective_client_id,
                        reason='response_enqueue_failed'
                    ))
                else:
                    logger.info(f"Enqueued response type '{response_message_dict.get('type')}' to to_frontend_queue for client {effective_client_id}.")

        except ValidationError as e:
            # This catches validation errors during initial message parsing or within command logic
            logger.error(f"Validation error during single message processing for message {msg_id}: {e}", exc_info=True)
            dlq_client_id = getattr(message, 'client_id', 'unknown_client_error')
            await self.safe_enqueue(self._dead_letter_queue, DeadLetterMessage(
                original_message=message.model_dump() if hasattr(message, 'model_dump') else {"raw_message": str(message)}, # Capture original message state
                error='message_validation_failed',
                details=str(e),
                timestamp=time.time(),
                client_id=dlq_client_id,
                reason='message_validation_failed'
            ))
        except Exception as e:
            # This catches any other unexpected errors during single message processing
            logger.error(f"Critical error during single message processing for message {msg_id}: {str(e)}", exc_info=True)
            dlq_client_id = getattr(message, 'client_id', 'unknown_client_error')
            await self.safe_enqueue(self._dead_letter_queue, DeadLetterMessage(
                original_message=message.model_dump() if hasattr(message, 'model_dump') else {"raw_message": str(message)}, # Capture original message state
                error='message_processing_exception',
                details=str(e),
                timestamp=time.time(),
                client_id=dlq_client_id,
                reason='message_processing_exception'
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
