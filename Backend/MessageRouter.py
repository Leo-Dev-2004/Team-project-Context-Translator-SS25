import asyncio
import logging
import time
import uuid
from typing import Optional, Dict, Any, Union

from Backend.models.message_types import (
    UniversalMessage,
    DeadLetterMessage, # Expected to be a subclass of UniversalMessage
    ProcessingPathEntry,
    ForwardingPathEntry,
    ErrorTypes, # Assuming this is an Enum
)
from Backend.core.Queues import queues # Assuming this provides MessageQueue instances

logger = logging.getLogger(__name__)

class MessageRouter:
    """
    The MessageRouter pulls UniversalMessages from the outgoing queue (from the dispatcher)
    and routes them to their final destination queues based on their 'destination' field.
    """
    def __init__(self):
        self._running = False
        self._routing_task: Optional[asyncio.Task] = None
        self._input_queue: Optional[asyncio.Queue] = None
        self._websocket_out_queue: Optional[asyncio.Queue] = None
        self._dead_letter_queue: Optional[asyncio.Queue] = None

    async def initialize(self):
        """Secure initialization and queue validation."""
        try:
            self._input_queue = queues.outgoing
            self._websocket_out_queue = queues.websocket_out
            self._dead_letter_queue = queues.dead_letter

            if None in (self._input_queue, self._websocket_out_queue, self._dead_letter_queue):
                raise RuntimeError("One or more MessageRouter queues not initialized correctly")

            logger.info("MessageRouter queues verified and initialized.")
        except Exception as e:
            logger.error(f"Failed to initialize MessageRouter: {str(e)}", exc_info=True)
            raise

    async def start(self):
        """Starts the main message routing loop as a background task."""
        if not self._running:
            self._running = True
            logger.info("Starting MessageRouter task.")
            self._routing_task = asyncio.create_task(self._route_messages())
            logger.info("MessageRouter task created and running in background.")
        else:
            logger.info("MessageRouter already running.")

    async def _route_messages(self):
        """Main routing loop with DLQ integration for unroutable messages."""
        logger.info("MessageRouter main loop started.")

        routed_count = 0
        last_log_time = time.time()

        while self._running:
            message: Optional[UniversalMessage] = None
            try:
                if self._input_queue is None or self._websocket_out_queue is None or self._dead_letter_queue is None:
                    logger.error("MessageRouter queues are not initialized. Cannot route messages.")
                    await asyncio.sleep(1)
                    continue

                try:
                    message = await asyncio.wait_for(self._input_queue.dequeue(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue
                if message is None:
                    await asyncio.sleep(0.1)
                    continue

                if message.processing_path is None:
                    message.processing_path = []
                message.processing_path.append(
                    ProcessingPathEntry(
                        processor="MessageRouter",
                        status="dequeued_for_routing",
                        details={"from_queue": "queues.outgoing"}
                    )
                )
                logger.debug(f"Router dequeued message {message.id} of type '{message.type}'. Destination: '{message.destination}'.")

                await self._process_single_message_for_routing(message)

                routed_count += 1

                if time.time() - last_log_time > 5:
                    logger.info(f"Routed {routed_count} messages in the last 5 seconds. Outgoing Queue Size: {self._input_queue.qsize()}")
                    last_log_time = time.time()
                    routed_count = 0

            except asyncio.CancelledError:
                logger.info("MessageRouter task was cancelled gracefully.")
                break
            except Exception as e:
                logger.error(f"Error during MessageRouter main loop: {str(e)}", exc_info=True)
                dlq_client_id = getattr(message, 'client_id', 'unknown_client_error') if message else 'unknown_client_error'
                original_msg_data = message.model_dump() if message and isinstance(message, UniversalMessage) else {"raw_message": str(message)}
                
                # Enqueue to Dead Letter Queue for unexpected loop errors
                assert self._dead_letter_queue is not None, "Dead Letter Queue must be initialized."
                await self._dead_letter_queue.enqueue(DeadLetterMessage(
                    id=str(uuid.uuid4()),
                    type=ErrorTypes.SYSTEM_ERROR.value,
                    client_id=dlq_client_id,
                    payload={"original_message_data": original_msg_data,
                             "reason": ErrorTypes.INTERNAL.value,
                             "error_details": {"exception": str(e), "component": "MessageRouter._route_messages_loop"}},
                    original_message=original_msg_data,
                    reason=ErrorTypes.INTERNAL.value,
                    error_details={"exception": str(e), "component": "MessageRouter._route_messages_loop"}
                ))
                await asyncio.sleep(1)

        logger.info("MessageRouter main loop stopped.")

    async def _process_single_message_for_routing(self, message: UniversalMessage) -> None:
        """
        Processes a single UniversalMessage to determine its routing destination.
        Sends unroutable messages to DLQ.
        """
        msg_id: str = message.id if message.id else "unknown"
        client_id: Optional[str] = message.client_id or "N/A"

        try:
            message.processing_path.append(
                ProcessingPathEntry(
                    processor="MessageRouter",
                    status="determining_route",
                    details={"destination_field": message.destination}
                )
            )

            # Routing Logic
            if message.destination == "frontend":
                logger.info(f"Message ID {msg_id} (Type: {message.type}) for client {client_id} identified for routing to WebSocket output queue.")
                
                message.forwarding_path.append(
                    ForwardingPathEntry(
                        processor="MessageRouter",
                        status="routed_to_websocket_output",
                        to_queue="queues.websocket_out"
                    )
                )
                assert self._websocket_out_queue is not None, "WebSocket output queue must be initialized."
                await self.safe_enqueue(self._websocket_out_queue, message)
                logger.debug(f"Message ID {msg_id} enqueued to 'queues.websocket_out'.")

            else:
                logger.warning(f"Unknown destination '{message.destination}' for message ID {msg_id}. Sending to DLQ.")
                message.processing_path.append(
                    ProcessingPathEntry(
                        processor="MessageRouter",
                        status="unknown_destination_dlq",
                        details={"unknown_destination": message.destination}
                    )
                )
                # Enqueue to Dead Letter Queue for unknown destinations
                assert self._dead_letter_queue is not None, "Dead Letter Queue must be initialized."
                await self.safe_enqueue(self._dead_letter_queue, DeadLetterMessage(
                    id=str(uuid.uuid4()),
                    type=ErrorTypes.ROUTING_ERROR.value, # Specific error type for routing issues
                    client_id=client_id,
                    payload={"original_message_data": message.model_dump(),
                             "reason": ErrorTypes.ROUTING_ERROR.value,
                             "error_details": {
                                 "type": "UnknownDestination",
                                 "message": f"No routing rule for destination: {message.destination}",
                                 "component": "MessageRouter._process_single_message_for_routing",
                                 "timestamp": time.time(),
                                 "client_id": client_id,
                                 "original_universal_message_id": message.id
                             }},
                    original_message=message.model_dump(),
                    reason=ErrorTypes.ROUTING_ERROR.value,
                    error_details={
                        "type": "UnknownDestination",
                        "message": f"No routing rule for destination: {message.destination}",
                        "component": "MessageRouter._process_single_message_for_routing",
                        "timestamp": time.time(),
                        "client_id": client_id,
                        "original_universal_message_id": message.id
                    }
                ))

            if not message.processing_path[-1].status == "unknown_destination_dlq":
                message.processing_path.append(
                    ProcessingPathEntry(
                        processor="MessageRouter",
                        status="routing_complete"
                    )
                )

        except ValidationError as e:
            logger.error(f"Validation error during message routing for message {msg_id}: {e}", exc_info=True)
            dlq_client_id = client_id
            # Enqueue to Dead Letter Queue for validation errors
            assert self._dead_letter_queue is not None, "Dead Letter Queue must be initialized."
            await self.safe_enqueue(self._dead_letter_queue, DeadLetterMessage(
                id=str(uuid.uuid4()),
                type=ErrorTypes.SYSTEM_ERROR.value,
                client_id=dlq_client_id,
                payload={"original_message_data": message.model_dump(),
                         "reason": ErrorTypes.VALIDATION.value,
                         "error_details": {"validation_error": str(e), "component": "MessageRouter._process_single_message_for_routing"}},
                original_message=message.model_dump(),
                reason=ErrorTypes.VALIDATION.value,
                error_details={"validation_error": str(e), "component": "MessageRouter._process_single_message_for_routing"}
            ))
        except Exception as e:
            logger.error(f"Critical error during single message routing for message {msg_id}: {str(e)}", exc_info=True)
            dlq_client_id = client_id
            # Enqueue to Dead Letter Queue for general exceptions
            assert self._dead_letter_queue is not None, "Dead Letter Queue must be initialized."
            await self.safe_enqueue(self._dead_letter_queue, DeadLetterMessage(
                id=str(uuid.uuid4()),
                type=ErrorTypes.SYSTEM_ERROR.value,
                client_id=dlq_client_id,
                payload={"original_message_data": message.model_dump(),
                         "reason": ErrorTypes.INTERNAL.value,
                         "error_details": {"exception": str(e), "component": "MessageRouter._process_single_message_for_routing"}},
                original_message=message.model_dump(),
                reason=ErrorTypes.INTERNAL.value,
                error_details={"exception": str(e), "component": "MessageRouter._process_single_message_for_routing"}
            ))

    async def safe_enqueue(self, queue, message: Union[UniversalMessage, DeadLetterMessage]) -> bool:
        """Thread-safe enqueue with error handling."""
        try:
            if queue:
                if not isinstance(message, (UniversalMessage, DeadLetterMessage)):
                    logger.error(f"Attempted to enqueue unsupported message type to queue in MessageRouter: {type(message).__name__}. Message: {message}")
                    return False
                
                await queue.enqueue(message)
                return True
            logger.warning("Attempted to enqueue to an uninitialized queue in MessageRouter.")
            return False
        except Exception as e:
            logger.error(f"Safe Enqueue failed in MessageRouter for message ID {getattr(message, 'id', 'N/A')}: {str(e)}", exc_info=True)
            return False

    async def stop(self):
        """Graceful shutdown for the MessageRouter."""
        if self._running:
            self._running = False
            logger.debug("MessageRouter shutdown initiated. Waiting for tasks to complete...")
            if self._routing_task:
                self._routing_task.cancel()
                try:
                    await self._routing_task
                except asyncio.CancelledError:
                    pass
            logger.info("MessageRouter shutdown complete.")
        else:
            logger.info("MessageRouter was not running.")