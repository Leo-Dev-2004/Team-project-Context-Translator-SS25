import asyncio
import copy
import logging
import time
import uuid
from typing import Optional, Dict, Any, Union, cast
from pydantic import ValidationError

from Backend.models.UniversalMessage import (
    UniversalMessage,
    DeadLetterMessage,
    ProcessingPathEntry,
    ForwardingPathEntry,
    ErrorTypes,
)
# Corrected import for the abstract queue type
from Backend.queues.QueueTypes import AbstractMessageQueue # Changed from MessageQueue

from Backend.core.Queues import queues

logger = logging.getLogger(__name__)

class BackendServiceDispatcher:
    def __init__(self,
                 incoming_queue: AbstractMessageQueue, # Corrected type hint
                 outgoing_queue: AbstractMessageQueue, # Corrected type hint
                 websocket_out_queue: AbstractMessageQueue, # Corrected type hint
                 dead_letter_queue: AbstractMessageQueue): # Corrected type hint
        self._running = False
        self._processing_task: Optional[asyncio.Task] = None
        self._dlq_monitor_task: Optional[asyncio.Task] = None
        self._input_queue = incoming_queue
        self._output_queue = outgoing_queue
        self._dead_letter_queue = dead_letter_queue
        logger.info("BackendServiceDispatcher initialized with queues.")

    async def initialize(self):
        """Perform any async initialization or final queue validation needed."""
        logger.info("BackendServiceDispatcher performing async initialization.")
        if None in (self._input_queue, self._output_queue, self._dead_letter_queue):
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

            if self._dlq_monitor_task:
                self._dlq_monitor_task.cancel()
                try:
                    await self._dlq_monitor_task
                except asyncio.CancelledError:
                    logger.info("BackendServiceDispatcher DLQ monitor task cancelled gracefully.")
                except Exception as e:
                    logger.error(f"Error cancelling DLQ monitor task: {e}", exc_info=True)
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
            self._dlq_monitor_task = asyncio.create_task(self.monitor_dead_letter_queue_task())
            logger.info("BackendServiceDispatcher and Dead Letter Queue monitor tasks created and running in background.")
        else:
            logger.info("BackendServiceDispatcher already running.")

    async def _process_messages(self):
        """Main processing loop with robust error handling, now integrating DLQ."""
        logger.info("BackendServiceDispatcher main loop started.")
        processed_count = 0
        last_log_time = time.time()

        while self._running:
            message: Optional[UniversalMessage] = None
            try:
                if self._input_queue is None or self._output_queue is None or self._dead_letter_queue is None:
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
                logger.debug(f"Dispatcher dequeued message {message.id} of type '{message.type}'. Client ID: {message.client_id}.")

                response_message: Optional[UniversalMessage] = await self._process_single_message(message)

                if response_message:
                    assert self._output_queue is not None, "Output queue must be initialized before sending messages"
                    await self.safe_enqueue(self._output_queue, response_message)
                    logger.debug(f"Dispatcher enqueued response message {response_message.id} of type '{response_message.type}' to outgoing queue.")

                processed_count += 1

                if time.time() - last_log_time > 5:
                    logger.info(f"Processed {processed_count} messages in the last 5 seconds. Incoming Queue Size: {self._get_input_queue_size()}")
                    last_log_time = time.time()
                    processed_count = 0

            except asyncio.CancelledError:
                logger.info("BackendServiceDispatcher task was cancelled gracefully.")
                break
            except Exception as e:
                logger.error(f"Error during BackendServiceDispatcher main loop: {str(e)}", exc_info=True)
                dlq_client_id = getattr(message, 'client_id', 'unknown_client_error') if message else 'unknown_client_error'
                original_msg_data = message.model_dump() if message and isinstance(message, UniversalMessage) else {"raw_message_unparseable": str(message)}

                assert self._dead_letter_queue is not None, "Dead Letter Queue must be initialized."
                await self._dead_letter_queue.enqueue(DeadLetterMessage(
                    origin="BackendServiceDispatcher",
                    destination="dead_letter_queue",
                    original_message_raw=original_msg_data,
                    type=ErrorTypes.SYSTEM_ERROR.value,
                    client_id=dlq_client_id,
                    reason=f"Dispatcher loop error: {str(e)}",
                    error_details={"exception_type": type(e).__name__, "message": str(e), "component": "BackendServiceDispatcher._process_messages_loop"}
                ))
                await asyncio.sleep(1)

        logger.info("BackendServiceDispatcher main loop stopped.")

    async def monitor_dead_letter_queue_task(self):
        """
        Background task to monitor the dead_letter_queue for unprocessable messages.
        Handles both DeadLetterMessage and potential UniversalMessage.
        """
        logger.info("Starting Dead Letter Queue monitor task.")
        if self._dead_letter_queue is None:
            logger.error("Dead Letter Queue is not initialized. Cannot monitor.")
            return

        while self._running:
            try:
                # This dequeued_item can now be UniversalMessage or DeadLetterMessage
                dequeued_item: Union[UniversalMessage, DeadLetterMessage, None] = await asyncio.wait_for(self._dead_letter_queue.dequeue(), timeout=1.0)

                if dequeued_item:
                    # Safely check the type at runtime
                    if isinstance(dequeued_item, DeadLetterMessage):
                        message: DeadLetterMessage = dequeued_item # Assign to a DeadLetterMessage
                        logger.critical(
                            f"Dead Letter Queue received message: {getattr(message, 'id', 'N/A')} "
                            f"of type {getattr(message, 'type', 'N/A')}. "
                            f"Reason: {message.reason}. "
                            f"Error Details: {message.error_details}. "
                            f"Original Message: {getattr(message, 'original_message_raw', 'N/A')}"
                        )
                    elif isinstance(dequeued_item, UniversalMessage):
                        # Handle cases where a UniversalMessage was mistakenly enqueued to DLQ
                        logger.warning(
                            f"DLQ dequeued a UniversalMessage (ID: {dequeued_item.id}, Type: {dequeued_item.type}) "
                            f"instead of a DeadLetterMessage. Re-wrapping it for consistent DLQ handling."
                        )
                        dlq_client_id = getattr(dequeued_item, 'client_id', 'N/A')
                        # Create a new DeadLetterMessage to properly log/handle this unexpected type
                        re_wrapped_dlq_message = DeadLetterMessage(
                            origin="DLQ_Monitor",
                            destination="dead_letter_queue",
                            original_message_raw=dequeued_item.model_dump(),
                            type=ErrorTypes.SYSTEM_ERROR.value, # Categorize as a system error for consistency
                            client_id=dlq_client_id,
                            reason="UniversalMessage found in DLQ without DeadLetterMessage wrapper.",
                            error_details={"original_type": dequeued_item.type, "message_id": dequeued_item.id, "component": "DLQ_Monitor_Unexpected_Type"}
                        )
                        # Log the re-wrapped message (you might also re-enqueue it if your DLQ stores only DLMs)
                        logger.critical(
                            f"DLQ Monitor processing re-wrapped DLM: {getattr(re_wrapped_dlq_message, 'id', 'N/A')} "
                            f"of type {getattr(re_wrapped_dlq_message, 'type', 'N/A')}. "
                            f"Reason: {re_wrapped_dlq_message.reason}. "
                            f"Error Details: {re_wrapped_dlq_message.error_details}. "
                            f"Original Message: {getattr(re_wrapped_dlq_message, 'original_message_raw', 'N/A')}"
                        )
                    else:
                        logger.critical(f"DLQ dequeued an unhandled item type: {type(dequeued_item)}. Data: {dequeued_item}")
                        # If you have other types that could end up here, handle them or log them.
                        continue # Skip to the next iteration

                else:
                    logger.debug("Queue 'dead_letter' empty, waiting to dequeue...")
                await asyncio.sleep(0.5)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                logger.info("Dead Letter Queue monitor task cancelled.")
                break
            except Exception as e:
                logger.error(f"Error in Dead Letter Queue monitor task: {e}", exc_info=True)
                await asyncio.sleep(5)
        logger.info("Dead Letter Queue monitor task stopped.")


    async def _process_single_message(self, message: UniversalMessage) -> Optional[UniversalMessage]:
            """
            Processes a single UniversalMessage. Directs invalid/unhandled messages to DLQ.
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
                            from_queue=message.origin, # Corrected: use message.origin directly
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
                            from_queue=message.origin, # Corrected: use message.origin directly
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
                            from_queue=message.origin, # Corrected: use message.origin directly
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
                    logger.warning(f"Unknown UniversalMessage type: {message.type} from client {client_id}. Sending to DLQ.")
                    assert self._dead_letter_queue is not None, "Dead Letter Queue must be initialized."
                    await self.safe_enqueue(self._dead_letter_queue, DeadLetterMessage(
                        type=ErrorTypes.UNKNOWN_MESSAGE_TYPE.value,
                        origin="BackendServiceDispatcher",
                        destination="dead_letter_queue",
                        client_id=client_id,
                        payload={"original_message_data": message.model_dump(),
                                "reason": ErrorTypes.UNKNOWN_MESSAGE_TYPE.value,
                                "error_details": {
                                    "type": "UnknownUniversalMessageType",
                                    "message": f"No specific handler found for UniversalMessage type: {message.type}",
                                    "component": "BackendServiceDispatcher._process_single_message",
                                    "timestamp": time.time(),
                                    "client_id": client_id,
                                    "original_universal_message_id": message.id
                                }},
                        original_message_raw=message.model_dump(),
                        reason=ErrorTypes.UNKNOWN_MESSAGE_TYPE.value,
                        error_details={
                            "type": "UnknownUniversalMessageType",
                            "message": f"No specific handler found for UniversalMessage type: {message.type}",
                            "component": "BackendServiceDispatcher._process_single_message",
                            "timestamp": time.time(),
                            "client_id": client_id,
                            "original_universal_message_id": message.id
                        }
                    ))
                    return None

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
                    destination="frontend"
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
                dlq_client_id = client_id or 'unknown_client_error'
                assert self._dead_letter_queue is not None, "Dead Letter Queue must be initialized."
                await self.safe_enqueue(self._dead_letter_queue, DeadLetterMessage(
                    id=str(uuid.uuid4()),
                    type=ErrorTypes.VALIDATION.value,
                    origin="BackendServiceDispatcher",
                    destination="dead_letter_queue",
                    client_id=dlq_client_id,
                    payload={"original_message_data": message.model_dump(),
                            "reason": ErrorTypes.VALIDATION.value,
                            "error_details": {"validation_error": str(e), "component": "BackendServiceDispatcher._process_single_message"}},
                    original_message_raw=message.model_dump(),
                    reason=ErrorTypes.VALIDATION.value,
                    error_details={"validation_error": str(e), "component": "BackendServiceDispatcher._process_single_message"}
                ))
                return None
            except Exception as e:
                logger.error(f"Critical error during single message processing for message {msg_id}: {str(e)}", exc_info=True)
                dlq_client_id = client_id or 'unknown_client_error'
                assert self._dead_letter_queue is not None, "Dead Letter Queue must be initialized."
                await self.safe_enqueue(self._dead_letter_queue, DeadLetterMessage(
                    id=str(uuid.uuid4()),
                    type=ErrorTypes.SYSTEM_ERROR.value,
                    origin="BackendServiceDispatcher",
                    destination="dead_letter_queue",
                    client_id=dlq_client_id,
                    payload={"original_message_data": message.model_dump(),
                            "reason": ErrorTypes.SYSTEM_ERROR.value,
                            "error_details": {"exception": str(e), "component": "BackendServiceDispatcher._process_single_message"}},
                    original_message_raw=message.model_dump(),
                    reason=ErrorTypes.SYSTEM_ERROR.value,
                    error_details={"exception": str(e), "component": "BackendServiceDispatcher._process_single_message"}
                ))
                return None

    async def _send_to_dlq(self, message: UniversalMessage, reason: str, error_type: ErrorTypes):
        """Sends a message to the Dead Letter Queue.
        This is a helper function to avoid code duplication.
        """
        logger.warning(
            f"Sending message (ID: {message.id}, Type: {message.type}) to DLQ. "
            f"Reason: {reason}. Error Type: {error_type.value}"
        )
        try:
            dlq_message = DeadLetterMessage(
                id=str(uuid.uuid4()),
                type=error_type.value,
                origin="BackendServiceDispatcher",
                destination="dead_letter_queue",
                original_message_raw=message.model_dump(),
                reason=reason,
                client_id=getattr(message, "client_id", None),
                error_details={"error_type": error_type.value, "dispatcher_error": reason},
              )
            assert self._dead_letter_queue is not None, "Dead Letter Queue must be initialized."
            await self._dead_letter_queue.enqueue(dlq_message)
            logger.info(f"Message {message.id} successfully sent to Dead Letter Queue.")
        except Exception as e:
            logger.critical(f"FATAL: Failed to send message {message.id} to Dead Letter Queue: {e}", exc_info=True)


    async def safe_enqueue(self, queue: AbstractMessageQueue, message: Union[UniversalMessage, DeadLetterMessage]) -> bool: # Corrected type hint
        """Thread-safe enqueue with error handling, ensuring type safety."""
        try:
            if queue:
                if not isinstance(message, (UniversalMessage, DeadLetterMessage)):
                    logger.error(f"Attempted to enqueue unsupported message type to queue in BackendServiceDispatcher: {type(message).__name__}. Message: {message}")
                    return False

                await queue.enqueue(message)
                return True
            logger.warning("Attempted to enqueue to an uninitialized queue in BackendServiceDispatcher.")
            return False
        except Exception as e:
             logger.error(f"Safe Enqueue failed in BackendServiceDispatcher for message ID {getattr(message, 'id', 'N/A')}: {str(e)}", exc_info=True)
             return False