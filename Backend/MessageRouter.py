# Backend/MessageRouter.py

import asyncio
import logging
import time
from typing import Dict, Any, Optional
from pydantic import ValidationError

# Import UniversalMessage and its related models
from Backend.models.UniversalMessage import (
    UniversalMessage,
    ProcessingPathEntry,
    ForwardingPathEntry,
    DeadLetterMessage,
    ErrorTypes
)

# Import the global queues instance
from Backend.core.Queues import queues
from Backend.queues.QueueTypes import AbstractMessageQueue

logger = logging.getLogger(__name__)

class MessageRouter:
    """
    The MessageRouter is responsible for routing UniversalMessages between different
    queues and services based on their 'type' and 'destination' fields.
    It acts as a central hub for message flow management.
    """

    def __init__(self):
        self._input_queue: AbstractMessageQueue = queues.incoming
        self._output_queue: AbstractMessageQueue = queues.outgoing
        self._websocket_out_queue: AbstractMessageQueue = queues.websocket_out
        self._dead_letter_queue: AbstractMessageQueue = queues.dead_letter

        self._running = False
        self._router_task: Optional[asyncio.Task] = None
        logger.info("MessageRouter initialized with global queues.")

    async def start(self):
        """Starts the message routing process."""
        if not self._running:
            self._running = True
            logger.info("MessageRouter starting...")
            self._router_task = asyncio.create_task(self._route_messages())
            logger.info("MessageRouter started.")

    async def stop(self):
        """Stops the message routing process and waits for pending tasks."""
        if self._running:
            self._running = False
            logger.info("MessageRouter stopping...")
            if self._router_task:
                self._router_task.cancel()
                try:
                    await self._router_task
                except asyncio.CancelledError:
                    logger.info("MessageRouter task cancelled successfully.")
                finally:
                    self._router_task = None
            logger.info("MessageRouter stopped.")

    async def _route_messages(self):
        """Main loop for routing messages from the input queue."""
        logger.info("MessageRouter: Listening for messages on input queue...")
        while self._running:
            # Initialize message to None to ensure it's always bound
            message: Optional[UniversalMessage] = None
            try:
                # Dequeue from the input queue
                message = await self._input_queue.dequeue()

                logger.debug(
                    f"MessageRouter received message (ID: {message.id}, Type: {message.type}, "
                    f"Origin: {message.origin}, Destination: {message.destination})."
                )

                # Update processing path (Router is a processor in this context)
                message.processing_path.append(ProcessingPathEntry(
                    processor="MessageRouter",
                    status="received_for_routing",
                    timestamp=time.time(),
                    completed_at=None,
                    details=None
                ))

                await self._process_and_route_message(message)

            except asyncio.CancelledError:
                logger.info("MessageRouter loop cancelled.")
                break
            except Exception as e:
                logger.error(f"MessageRouter encountered unhandled error in main loop: {e}", exc_info=True)
                # If message is None, it means the error happened before dequeue
                if message is None:
                    problematic_message = UniversalMessage(
                        type=ErrorTypes.INTERNAL_SERVER_ERROR.value,
                        payload={"error": "Router loop unhandled exception: message not dequeued", "details": str(e)},
                        origin="MessageRouter",
                        destination="dead_letter_queue",
                        client_id=None # Or a default/system client ID if applicable
                    )
                else:
                    problematic_message = message

                await self._send_to_dlq(
                    message=problematic_message,
                    reason=f"Router loop unhandled exception: {e}",
                    error_type=ErrorTypes.INTERNAL_SERVER_ERROR
                )

    async def _process_and_route_message(self, message: UniversalMessage):
        """Processes a single message and routes it to the appropriate queue."""
        try:
            target_queue: Optional[AbstractMessageQueue] = None

            # Route based on message destination
            if message.destination == "backend.dispatcher":
                target_queue = self._output_queue
                logger.debug(f"Routing message {message.id} to backend.dispatcher.")
            elif message.destination == "frontend":
                target_queue = self._websocket_out_queue
                logger.debug(f"Routing message {message.id} to frontend.")
            elif message.destination == "dead_letter_queue":
                target_queue = self._dead_letter_queue
                logger.debug(f"Routing message {message.id} directly to dead_letter_queue.")
            else:
                logger.warning(
                    f"Unknown or unroutable message destination '{message.destination}' "
                    f"for message ID: {message.id}. Sending to Dead Letter Queue."
                )
                await self._send_to_dlq(
                    message=message,
                    reason=f"Unroutable destination: {message.destination}",
                    error_type=ErrorTypes.ROUTING_ERROR # Using ROUTING_ERROR for unroutable destinations
                )
                return

            if target_queue:
                # Update processing path before enqueuing
                message.processing_path.append(ProcessingPathEntry(
                    processor="MessageRouter",
                    status=f"routed_to_{target_queue.name}",
                    timestamp=time.time(),
                    completed_at=None,
                    details=None
                ))
                await target_queue.enqueue(message)
                logger.debug(f"Message {message.id} successfully enqueued to {target_queue.name}.")
            else:
                logger.error(f"No target queue determined for message ID: {message.id}. Sending to DLQ.")
                await self._send_to_dlq(
                    message=message,
                    reason="No target queue determined by router.",
                    error_type=ErrorTypes.ROUTING_ERROR
                )

        except ValidationError as ve:
            logger.error(f"Message validation error during routing for message ID: {message.id}. Error: {ve}", exc_info=True)
            await self._send_to_dlq(
                message=message,
                reason=f"Validation error during routing: {ve}",
                error_type=ErrorTypes.VALIDATION
            )
        except Exception as e:
            logger.error(f"Error processing and routing message ID: {message.id}. Error: {e}", exc_info=True)
            await self._send_to_dlq(
                message=message,
                reason=f"General error during routing: {e}",
                error_type=ErrorTypes.INTERNAL_SERVER_ERROR
            )

    async def _send_to_dlq(self, message: UniversalMessage, reason: str, error_type: ErrorTypes):
        """Sends a message to the Dead Letter Queue."""
        logger.warning(
            f"Sending message (ID: {message.id}, Type: {message.type}) to DLQ. "
            f"Reason: {reason}. Error Type: {error_type.value}"
        )
        try:
            dlq_message = DeadLetterMessage(
                type=error_type.value, # Use the provided error_type's value as the DLQ message type
                origin="MessageRouter",
                destination="dead_letter_queue",
                original_message_raw=message.model_dump(),
                reason=reason,
                client_id=message.client_id, # Directly access client_id from the message
                error_details={"error_type": error_type.value, "router_error": reason},
            )
            await self._dead_letter_queue.enqueue(dlq_message)
            logger.info(f"Message {message.id} successfully sent to Dead Letter Queue.")
        except Exception as e:
            logger.critical(f"FATAL: Failed to send message {message.id} to Dead Letter Queue: {e}", exc_info=True)