import asyncio
import copy
import logging
import time
import uuid
from typing import Optional, Dict, Any, cast
from pydantic import ValidationError

from ..queues.shared_queue import (
    get_to_backend_queue,
    get_to_frontend_queue,
    get_dead_letter_queue
)
from ..models.message_types import ProcessingPathEntry, WebSocketMessage, ErrorTypes
from ..dependencies import get_simulation_manager

logger = logging.getLogger(__name__)

class MessageProcessor:
    def __init__(self):
        self._running = False
        self._processing_task: Optional[asyncio.Task] = None
        self._input_queue: Optional[Any] = None
        self._output_queue: Optional[Any] = None
        self._dead_letter_queue: Optional[Any] = None

    async def initialize(self):
        """Sichere Initialisierung mit Queue-Validierung"""
        try:
            self._input_queue = get_to_backend_queue()
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
            return self._input_queue.size()
        return 0

    async def start(self):
        """Starts the main message processing loop as a background task."""
        if not self._running:
            self._running = True
            logger.info("Starting MessageProcessor task.")
            self._processing_task = asyncio.create_task(self._process_messages())
            logger.info("MessageProcessor task created and running in background.")
        else:
            logger.info("MessageProcessor already running.")

    async def _process_messages(self):
        """Main processing loop with robust error handling"""
        logger.info("MessageProcessor main loop started.")

        processed_count = 0
        last_log_time = time.time()

        while self._running:
            try:
                if self._input_queue is None or self._output_queue is None or self._dead_letter_queue is None:
                    logger.error("MessageProcessor queues are not initialized. Cannot process messages.")
                    await asyncio.sleep(1)
                    continue

                message = await self._input_queue.dequeue()
                logger.debug(f"MessageProcessor dequeued message {message.get('id', 'N/A')} of type '{message.get('type', 'N/A')}'.")

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
                await asyncio.sleep(1)

        logger.info("MessageProcessor main loop stopped.")

    async def _process_single_message(self, message: Dict) -> None:
        """Process messages with detailed tracing and response generation."""
        msg_id = message.get('id', 'unknown')
        msg_type = message.get('type', 'unknown')
        client_id = message.get('client_id', 'unknown')
        
        logger.debug(f"Processing message {msg_id} (type: {msg_type}, client: {client_id})")
        
        try:
            # Validate message structure
            if not isinstance(message, dict):
                raise ValueError("Message must be a dictionary")
            if 'type' not in message:
                raise ValueError("Message missing 'type' field")
            if 'data' not in message:
                raise ValueError("Message missing 'data' field")

            response_message_dict: Optional[Dict[str, Any]] = None

        try:
            msg: WebSocketMessage
            try:
                msg = WebSocketMessage.model_validate(message)
            except ValidationError as e:
                logger.error(f"Validation error for incoming WebSocket message: {e}", exc_info=True)
                await self.safe_enqueue(self._dead_letter_queue, {
                    'original_message': message,
                    'error': 'invalid_message_format',
                    'details': str(e),
                    'timestamp': time.time(),
                    'client_id': message.get('client_id', 'unknown_client')
                })
                return

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

            # --- Core Message Processing Logic based on 'type' ---
            if msg.type == 'ping':
                logger.info(f"MessageProcessor: Received ping from {effective_client_id}. Responding with pong.")
                response_message_dict = WebSocketMessage(
                    id=str(uuid.uuid4()),
                    type="pong",
                    data={"original_id": msg.id},
                    timestamp=time.time(),
                    client_id=effective_client_id,
                    processing_path=msg.processing_path,
                    forwarding_path=msg.forwarding_path
                ).model_dump()

            elif msg.type == 'command':
                command_name = msg.data.get('command')
                logger.info(f"MessageProcessor: Processing command '{command_name}' from {effective_client_id}")

                # Initialize response_type and response_data with default error values
                # This ensures they are always bound before the 'finally' block
                response_type: str = "error"
                response_data: Dict[str, Any] = {
                    "original_command": command_name,
                    "original_id": msg.id,
                    "client_id": effective_client_id,
                    "status": "failed",
                    "error": ErrorTypes.INTERNAL, # Default to internal error
                    "message": "An unhandled error occurred during command processing."
                }

                try:
                    sim_manager = get_simulation_manager(require_ready=True)

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

                    else:
                        # For unknown commands, set specific error message
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
                except KeyError as e: # This likely covers cases like command_name not being found in msg.data
                    logger.error(f"Missing data for command or command not found: {str(e)}", exc_info=True)
                    response_type = "error"
                    response_data.update({
                        "error": ErrorTypes.COMMAND_NOT_FOUND, # Changed from BAD_REQUEST as KeyError implies missing data
                        "message": f"Missing required data for command '{command_name}' or command not found in data: {str(e)}",
                        "status": "failed"
                    })
                except Exception as e:
                    logger.error(f"Command processing error: {str(e)}", exc_info=True)
                    # The default `response_data` already handles a generic internal error.
                    # Just update message if needed.
                    response_data.update({
                        "message": f"Internal server error during command processing: {str(e)}"
                    })
                    response_type = "error" # Ensure type is error

                finally:
                    # response_type and response_data are now guaranteed to be bound
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
                pass # Do nothing, just acknowledge

            elif msg.type == 'data':
                logger.info(f"MessageProcessor: Forwarding data message from {effective_client_id}")
                response_message_dict = WebSocketMessage(
                    type="data",
                    data=msg.data,
                    client_id=effective_client_id,
                    processing_path=msg.processing_path,
                    forwarding_path=msg.forwarding_path
                ).model_dump()

            else:
                logger.warning(f"MessageProcessor: Unhandled message type: '{msg.type}' from {effective_client_id}. Sending to Dead Letter Queue.")
                await self.safe_enqueue(self._dead_letter_queue, {
                    'original_message': message,
                    'error': 'unhandled_message_type',
                    'timestamp': time.time(),
                    'client_id': effective_client_id
                })

            # Enqueue response if generated
            if response_message_dict:
                if not await self.safe_enqueue(self._output_queue, response_message_dict):
                    logger.error(f"Failed to enqueue response message (type: {response_message_dict.get('type')}) to to_frontend_queue for client {effective_client_id}. Sending to DLQ.")
                    await self.safe_enqueue(self._dead_letter_queue, {
                        'original_message': response_message_dict,
                        'error': 'response_enqueue_failed',
                        'timestamp': time.time(),
                        'client_id': effective_client_id
                    })
                else:
                    logger.info(f"Enqueued response type '{response_message_dict.get('type')}' to to_frontend_queue for client {effective_client_id}.")

        except Exception as e:
            logger.error(f"Critical error during message processing for message {message.get('id', 'N/A')}: {str(e)}", exc_info=True)
            dlq_client_id = message.get('client_id', 'unknown_client_error')
            await self.safe_enqueue(self._dead_letter_queue, {
                'original_message': message,
                'error': 'processing_exception',
                'details': str(e),
                'timestamp': time.time(),
                'client_id': dlq_client_id
            })

    async def _safe_dequeue(self, queue) -> Optional[Dict]:
        """Thread-safe dequeue with error handling."""
        try:
            return await queue.dequeue() if queue else None
        except Exception as e:
            logger.warning(f"Safe Dequeue failed in MessageProcessor: {str(e)}")
            return None

    async def safe_enqueue(self, queue, message) -> bool:
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
            logger.info("MessageProcessor shutdown complete.")
        else:
            logger.info("MessageProcessor was not running.")
