import asyncio
import logging
import time
import uuid
from typing import Optional, Dict, Any, Union, cast
from pydantic import ValidationError

from Backend.models.UniversalMessage import (
    UniversalMessage,
    ProcessingPathEntry,
    ForwardingPathEntry,
    ErrorTypes, # Keep ErrorTypes if used for other error handling, otherwise remove if only for DLQ
)
# Corrected import for the abstract queue type
from Backend.queues.QueueTypes import AbstractMessageQueue

from Backend.core.Queues import queues

logger = logging.getLogger(__name__)

class BackendServiceDispatcher:
    def __init__(self,
                 incoming_queue: AbstractMessageQueue,
                 outgoing_queue: AbstractMessageQueue,
                 websocket_out_queue: AbstractMessageQueue):
        self._running = False
        self._processing_task: Optional[asyncio.Task] = None
        # Removed _dlq_monitor_task as DLQ is no longer used
        self._input_queue = incoming_queue
        self._output_queue = outgoing_queue
        self._websocket_out_queue = websocket_out_queue
        # Removed self._dead_letter_queue
        logger.info("BackendServiceDispatcher initialized with queues.")

    async def initialize(self):
        """Perform any async initialization or final queue validation needed."""
        logger.info("BackendServiceDispatcher performing async initialization.")
        # Removed _dead_letter_queue from the validation check
        if None in (self._input_queue, self._output_queue, self._websocket_out_queue): # Added websocket_out_queue to validation
            raise RuntimeError("One or more BackendServiceDispatcher queues were not set during __init__.")
        logger.info("BackendServiceDispatcher queues verified in initialize.")
        await asyncio.sleep(0.1)
        logger.info("BackendServiceDispatcher initialization complete.")

    async def stop(self):
        """Graceful shutdown for the BackendServiceDispatcher."""
        if self._running:
            self._running = False
            logger.debug("BackendServiceDispatcher shutdown initiated. Waiting for tasks to complete...")
            if self._processing_task:
                self._processing_task.cancel()
                try:
                    await self._processing_task
                except asyncio.CancelledError:
                    logger.info("BackendServiceDispatcher processing task cancelled gracefully.")
                except Exception as e:
                    logger.error(f"Error cancelling processing task: {e}", exc_info=True)

            # Removed _dlq_monitor_task cancellation
            logger.info("BackendServiceDispatcher shutdown complete.")
        else:
            logger.info("BackendServiceDispatcher was not running.")

    def _get_input_queue_size(self) -> int:
        """Returns the size of the input queue."""
        if self._input_queue:
            return self._input_queue.qsize()
        return 0

    async def start(self):
        """Starts the main message processing loop as a background task."""
        if not self._running:
            self._running = True
            logger.info("Starting BackendServiceDispatcher task.")
            self._processing_task = asyncio.create_task(self._process_messages())
            # Removed starting of DLQ monitor task
            logger.info("BackendServiceDispatcher processing task created and running in background.") # Adjusted log message
        else:
            logger.info("BackendServiceDispatcher already running.")

    async def _process_messages(self):
        """Main processing loop with robust error handling."""
        logger.info("BackendServiceDispatcher main loop started.")
        processed_count = 0
        last_log_time = time.time()

        while self._running:
            message: Optional[UniversalMessage] = None
            try:
                # Removed _dead_letter_queue from the queue initialization check
                if self._input_queue is None or self._output_queue is None or self._websocket_out_queue is None:
                    logger.error("BackendServiceDispatcher queues are not initialized. Cannot process messages.")
                    await asyncio.sleep(1)
                    continue

                try:
                    message = await asyncio.wait_for(self._input_queue.dequeue(), timeout=1.0)
                except asyncio.TimeoutError:
                    continue
                if message is None:
                    await asyncio.sleep(0.1)
                    continue

                if not hasattr(message, 'processing_path') or message.processing_path is None:
                    message.processing_path = []
                message.processing_path.append(
                    ProcessingPathEntry(
                        processor="BackendServiceDispatcher",
                        status="started",
                        completed_at=None,
                        details={"from_queue": "queues.incoming"}
                    )
                )
                # logger.debug(f"Dispatcher dequeued message {message.id} of type '{message.type}'. Client ID: {message.client_id}.")

                response_message: Optional[UniversalMessage] = await self._process_single_message(message)

                if response_message:
                    if response_message.destination == "frontend":
                        assert self._websocket_out_queue is not None, "WebSocket Out queue must be initialized before sending to frontend"
                        await self.safe_enqueue(self._websocket_out_queue, response_message)
                        logger.debug(f"Dispatcher enqueued response message {response_message.id} of type '{response_message.type}' to websocket_out_queue (for frontend).")
                    else:
                        assert self._output_queue is not None, "Output queue must be initialized before sending messages to other backend services"
                        await self.safe_enqueue(self._output_queue, response_message)
                        logger.debug(f"Dispatcher enqueued response message {response_message.id} of type '{response_message.type}' to outgoing queue (for backend).")

                processed_count += 1

                if time.time() - last_log_time > 5:
                    logger.info(f"Processed {processed_count} messages in the last 5 seconds. Incoming Queue Size: {self._get_input_queue_size()}. WebSocket Out Queue Size: {self._websocket_out_queue.qsize()}.")
                    last_log_time = time.time()
                    processed_count = 0

            except asyncio.CancelledError:
                logger.info("BackendServiceDispatcher task was cancelled gracefully.")
                break
            except Exception as e:
                logger.error(f"Error during BackendServiceDispatcher main loop: {str(e)}", exc_info=True)
                # Removed DLQ enqueueing for general errors. Consider alternative error logging/handling.
                await asyncio.sleep(1)

        logger.info("BackendServiceDispatcher main loop stopped.")

    # Removed the entire monitor_dead_letter_queue_task function as it's no longer needed.
    # Removed the second while self._running loop that contained the DLQ monitor logic from _process_messages.

    async def _process_single_message(self, message: UniversalMessage) -> Optional[UniversalMessage]:
        """
        Processes a single UniversalMessage. No longer directs invalid/unhandled messages to DLQ.
        """
        msg_id: str = message.id if message.id else "unknown"
        client_id: Optional[str] = message.client_id or "N/A"

        try:
            logger.info(f"Dispatcher processing UniversalMessage ID: {msg_id}, Type: {message.type}, Client ID: {client_id}")

            if message.processing_path is None:
                message.processing_path = []
            message.processing_path.append(
                ProcessingPathEntry(
                    processor="BackendServiceDispatcher",
                    status="processing",
                    completed_at=None,
                    details={"message_type_handled": message.type}
                )
            )

            if message.forwarding_path is None:
                message.forwarding_path = []
            if message.origin == "frontend":
                message.forwarding_path.append(
                    ForwardingPathEntry(
                        from_queue=message.origin,
                        to_queue="backend.dispatcher",
                        details={"dequeued_from_frontend_websocket_manager": "queues.incoming"}
                    )
                )

            response_payload: Dict[str, Any] = {}
            response_type: str = "system.response"

            if message.type == "frontend.ready_ack":
                logger.info(f"Received 'frontend.ready_ack' from client {client_id}. Frontend is ready.")
                response_type = "backend.ready_confirm"
                response_payload = {"message": "Backend received your ready signal!", "timestamp": time.time()}

            elif message.type == "ping":
                logger.debug(f"Received 'ping' from client {client_id}. Preparing 'pong'.")
                response_type = "pong"
                response_payload = {"timestamp": time.time()}

            elif message.type == "user_input":
                logger.info(f"Received user input from {client_id}: {message.payload.get('text')}")
                response_type = "system.acknowledgement"
                response_payload = {"message": "User input received by dispatcher for further processing."}

                if message.forwarding_path is None:
                    message.forwarding_path = []
                message.forwarding_path.append(
                    ForwardingPathEntry(
                        from_queue=message.origin,
                        to_queue="backend.some_logic_service",
                        details={"forwarding_user_input": "backend.some_logic_service"}
                    )
                )

            elif message.type == "start_simulation":
                logger.info(f"Starting simulation command from client {client_id} with data: {message.payload}")
                response_type = "system.acknowledgement"
                response_payload = {"message": "Simulation start command received."}

                if message.forwarding_path is None:
                    message.forwarding_path = []
                message.forwarding_path.append(
                    ForwardingPathEntry(
                        from_queue=message.origin,
                        to_queue="backend.simulation_manager",
                        details={"forwarding_to_simulation_manager": "backend.simulation_manager"}
                    )
                )

            elif message.type == "frontend.init":
                logger.info(f"Frontend initialized by client {client_id} with message: {message.payload.get('message')}")
                response_type = "system.acknowledgement"
                response_payload = {"message": "Frontend initialization acknowledged."}

            elif message.type == "system_message":
                logger.info(f"Received system message from client {client_id}: {message.payload.get('text')}")
                response_type = "system.acknowledgement"
                response_payload = {"message": "System message acknowledged."}

            else:
                logger.warning(f"Unknown UniversalMessage type: {message.type} from client {client_id}. Message will not be processed further.")
                # Removed DLQ enqueueing for unknown message types.
                return None # Return None if message type is unhandled

            message.processing_path.append(
                ProcessingPathEntry(
                    processor="BackendServiceDispatcher",
                    status="handled",
                    completed_at=None,
                    details={"handled_type": message.type}
                )
            )

            response_universal_message = UniversalMessage(
                id=f"{response_type}-{str(uuid.uuid4())}",
                type=response_type,
                client_id=client_id,
                timestamp=time.time(),
                payload=response_payload,
                origin="BackendServiceDispatcher",
                destination="frontend" # Assuming response always goes to frontend here
            )
            response_universal_message.processing_path.append(
                ProcessingPathEntry(
                    processor="BackendServiceDispatcher",
                    status="enqueued",
                    completed_at=None,
                    details={"to_queue": "queues.outgoing"}
                )
            )
            return response_universal_message

        except ValidationError as e:
            logger.error(f"Validation error during single message processing for message {msg_id}: {e}", exc_info=True)
            # Removed DLQ enqueueing for validation errors.
            return None
        except Exception as e:
            logger.error(f"Critical error during single message processing for message {msg_id}: {str(e)}", exc_info=True)
            # Removed DLQ enqueueing for critical errors.
            return None

    # Removed the entire _send_to_dlq function.

    async def safe_enqueue(self, queue: AbstractMessageQueue, message: UniversalMessage) -> bool: # Corrected type hint, removed DeadLetterMessage
        """Thread-safe enqueue with error handling, ensuring type safety."""
        try:
            if queue:
                if not isinstance(message, UniversalMessage): # Only UniversalMessage expected now
                    logger.error(f"Attempted to enqueue unsupported message type to queue in BackendServiceDispatcher: {type(message).__name__}. Message: {message}")
                    return False

                await queue.enqueue(message)
                return True
            logger.warning("Attempted to enqueue to an uninitialized queue in BackendServiceDispatcher.")
            return False
        except Exception as e:
             logger.error(f"Safe Enqueue failed in BackendServiceDispatcher for message ID {getattr(message, 'id', 'N/A')}: {str(e)}", exc_info=True)
             return False
