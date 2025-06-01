# backend/src/modules/MessageProcessor.py

import asyncio
import copy
import logging
import time
import uuid
from typing import Optional, Dict, Any, cast
from pydantic import ValidationError

from ..queues.shared_queue import (
    get_from_frontend_queue,
    get_to_backend_queue, # This queue is not used in MessageProcessor based on your code
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
        # You previously used self.qm.dead_letter_queue in monitor_dead_letter_queue_task
        # If your MessageProcessor expects a queue manager, you should pass it
        # Otherwise, the 'qm' attribute will not exist.
        # For now, let's assume direct queue access via self._dead_letter_queue is intended.
        # So, the 'self.qm' part in monitor_dead_letter_queue_task would need to be changed to 'self'.

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
            return self._input_queue.size()
        return 0

    async def start(self):
        """Starts the main message processing loop as a background task."""
        if not self._running:
            self._running = True
            logger.info("Starting MessageProcessor task.")
            self._processing_task = asyncio.create_task(self._process_messages())
            # Start the dead letter queue monitor task here as well
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
                message_to_dlq = locals().get('message', {'id': 'N/A', 'type': 'unknown'})
                await self.safe_enqueue(self._dead_letter_queue, {
                    'original_message': message_to_dlq,
                    'error': 'processing_exception',
                    'details': str(e),
                    'timestamp': time.time(),
                    'client_id': message_to_dlq.get('client_id', 'unknown_client_error')
                })
                await asyncio.sleep(1)

        logger.info("MessageProcessor main loop stopped.")

    # --- THIS IS THE CORRECTED INDENTATION ---
    async def monitor_dead_letter_queue_task(self):
        """
        Background task to monitor the dead_letter_queue for unprocessable messages.
        """
        logger.info("Starting Dead Letter Queue monitor task.")
        # Make sure to use self._dead_letter_queue here, not self.qm.dead_letter_queue
        # as self.qm is not defined in this MessageProcessor's __init__
        if self._dead_letter_queue is None:
            logger.error("Dead Letter Queue is not initialized. Cannot monitor.")
            return # Exit if queue not ready

        while self._running: # Use the existing running flag of the MessageProcessor
            try:
                message = await self._dead_letter_queue.dequeue()
                
                if message:
                    logger.warning(f"Dead Letter Queue received message: {message.get('id', 'N/A')} of type {message.get('type', 'N/A')}. Content: {message}")
                    # Hier könntest du weitere Logik hinzufügen
                else:
                    logger.debug("Queue 'dead_letter' empty, waiting to dequeue...")

            except asyncio.CancelledError:
                logger.info("Dead Letter Queue monitor task cancelled.")
                break
            except Exception as e:
                logger.error(f"Error in Dead Letter Queue monitor task: {e}", exc_info=True)
                await asyncio.sleep(5)
        logger.info("Dead Letter Queue monitor task stopped.")
    # --- END OF CORRECTED INDENTATION ---

    async def _process_single_message(self, message: Dict) -> None:
        await asyncio.sleep(1)
        """Process messages with detailed tracing and response generation."""
        msg_id = message.get('id', 'unknown')
        msg_type = message.get('type', 'unknown')
        client_id = message.get('client_id', 'unknown')
        
        logger.debug(f"Processing message {msg_id} (type: {msg_type}, client: {client_id})")
        
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

            if msg.type == 'ping':
                logger.info(f"MessageProcessor: Received ping from {effective_client_id}")
                try:
                    # Create pong response
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
                    
                    # Enqueue the pong response
                    await self.safe_enqueue(
                        self._output_queue,
                        pong_message.model_dump()
                    )
                    logger.info(f"Enqueued pong response for ping from {effective_client_id}")
                    
                except ValidationError as e:
                    logger.error(f"Failed to validate pong message: {e}", exc_info=True)
                    await self.safe_enqueue(
                        self._dead_letter_queue,
                        {
                            'original_message': message,
                            'error': 'pong_validation_failed',
                            'details': str(e),
                            'timestamp': time.time(),
                            'client_id': effective_client_id
                        }
                    )
                except Exception as e:
                    logger.error(f"Unexpected error handling ping: {e}", exc_info=True)
                    await self.safe_enqueue(
                        self._dead_letter_queue,
                        {
                            'original_message': message,
                            'error': 'ping_processing_error',
                            'details': str(e),
                            'timestamp': time.time(),
                            'client_id': effective_client_id
                        }
                    )
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
                pass

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

            if response_message_dict:
                try:
                    msg = WebSocketMessage.model_validate(response_message_dict)
                    if not await self.safe_enqueue(self._output_queue, msg):
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
            # Also cancel the DLQ monitor task
            if hasattr(self, '_dlq_monitor_task') and self._dlq_monitor_task:
                self._dlq_monitor_task.cancel()
                try:
                    await self._dlq_monitor_task
                except asyncio.CancelledError:
                    pass
            logger.info("MessageProcessor shutdown complete.")
        else:
            logger.info("MessageProcessor was not running.")
