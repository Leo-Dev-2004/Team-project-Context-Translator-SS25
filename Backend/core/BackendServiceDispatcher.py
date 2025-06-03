import asyncio
import copy
import logging
import time
import uuid
from typing import Optional, Dict, Any, Union, cast
from pydantic import ValidationError

from Backend.models.UniversalMessage import (
    UniversalMessage,
    DeadLetterMessage, # Expected to be a subclass of UniversalMessage
    ProcessingPathEntry,
    ForwardingPathEntry,
    ErrorTypes, # Assuming this is an Enum
)

from Backend.core.Queues import queues # Assuming this provides MessageQueue instances

logger = logging.getLogger(__name__)

class BackendServiceDispatcher:
    def __init__(self):
        self._running = False
        self._processing_task: Optional[asyncio.Task] = None
        self._dlq_monitor_task: Optional[asyncio.Task] = None # Added for DLQ monitoring
        self._input_queue: Optional[Any] = None
        self._output_queue: Optional[Any] = None
        self._dead_letter_queue: Optional[Any] = None

    async def initialize(self):
        """Secure initialization with Queue validation."""
        try:
            self._input_queue = queues.incoming
            self._output_queue = queues.outgoing
            self._dead_letter_queue = queues.dead_letter

            if None in (self._input_queue, self._output_queue, self._dead_letter_queue):
                raise RuntimeError("One or more BackendServiceDispatcher queues not initialized correctly")

            logger.info("BackendServiceDispatcher queues verified and initialized.")
        except Exception as e:
            logger.error(f"Failed to initialize BackendServiceDispatcher: {str(e)}", exc_info=True)
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
            logger.info("Starting BackendServiceDispatcher task.")
            self._processing_task = asyncio.create_task(self._process_messages())
            self._dlq_monitor_task = asyncio.create_task(self.monitor_dead_letter_queue_task()) # Start DLQ monitor
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

                # Ensure processing_path exists and is a list before appending
                # Pydantic's default_factory ensures this, but defensive check
                if not hasattr(message, 'processing_path') or message.processing_path is None:
                    message.processing_path = []
                message.processing_path.append(
                    ProcessingPathEntry(
                        processor_name="BackendServiceDispatcher", # Using processor_name
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
                original_msg_data = message.model_dump() if message and isinstance(message, UniversalMessage) else {"raw_message": str(message)}
                
                # Enqueue to Dead Letter Queue for unexpected loop errors
                assert self._dead_letter_queue is not None, "Dead Letter Queue must be initialized."
                await self._dead_letter_queue.enqueue(DeadLetterMessage(
                    id=str(uuid.uuid4()),
                    type=ErrorTypes.SYSTEM_ERROR.value,
                    client_id=dlq_client_id,
                    payload={"original_message_data": original_msg_data, # `payload` is now a valid field
                             "reason": ErrorTypes.SYSTEM_ERROR.value,
                             "error_details": {"exception": str(e), "component": "BackendServiceDispatcher._process_messages_loop"}},
                    original_message=original_msg_data,
                    reason=ErrorTypes.SYSTEM_ERROR.value,
                    error_details={"exception": str(e), "component": "BackendServiceDispatcher._process_messages_loop"}
                ))
                await asyncio.sleep(1)

        logger.info("BackendServiceDispatcher main loop stopped.")

    async def monitor_dead_letter_queue_task(self):
        """
        Background task to monitor the dead_letter_queue for unprocessable messages.
        Now explicitly expects DeadLetterMessage (inheriting from UniversalMessage).
        """
        logger.info("Starting Dead Letter Queue monitor task.")
        if self._dead_letter_queue is None:
            logger.error("Dead Letter Queue is not initialized. Cannot monitor.")
            return

        while self._running:
            try:
                message: Optional[DeadLetterMessage] = await asyncio.wait_for(self._dead_letter_queue.dequeue(), timeout=1.0)
                
                if message:
                    logger.critical(
                        f"Dead Letter Queue received message: {getattr(message, 'id', 'N/A')} "
                        f"of type {getattr(message, 'type', 'N/A')}. "
                        f"Reason: {message.reason}. "
                        f"Error Details: {message.error_details}. "
                        f"Original Message: {message.original_message}"
                    )
                    # Here you might add logic to store to database, trigger alerts, etc.
                else:
                    logger.debug("Queue 'dead_letter' empty, waiting to dequeue...")
                await asyncio.sleep(0.5)
            except asyncio.TimeoutError:
                continue # Check self._running and loop again
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

            # Ensure processing_path exists and is a list before appending
            if not hasattr(message, 'processing_path') or message.processing_path is None:
                message.processing_path = []
            message.processing_path.append(
                ProcessingPathEntry(
                    processor_name="BackendServiceDispatcher", # Using processor_name
                    details={"message_type_handled": message.type}
                )
            )

            # Ensure forwarding_path exists and is a list before appending
            if not hasattr(message, 'forwarding_path') or message.forwarding_path is None:
                message.forwarding_path = []
            if message.origin == "frontend":
                message.forwarding_path.append(
                    ForwardingPathEntry(
                        destination="BackendServiceDispatcher", # Using destination
                        details={"dequeued_from_frontend_websocket_manager": "queues.incoming"}
                    )
                )

            response_payload: Dict[str, Any] = {}
            response_type: str = "system.response"

            # --- Handle specific UniversalMessage types ---
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
                
                # Ensure forwarding_path exists and is a list before appending
                if not hasattr(message, 'forwarding_path') or message.forwarding_path is None:
                    message.forwarding_path = []
                message.forwarding_path.append(
                    ForwardingPathEntry(
                        destination="backend.some_logic_service", # Using destination
                        details={"forwarding_user_input": "backend.some_logic_service"}
                    )
                )

            elif message.type == "start_simulation":
                logger.info(f"Starting simulation command from client {client_id} with data: {message.payload}")
                response_type = "system.acknowledgement"
                response_payload = {"message": "Simulation start command received."}

                # Ensure forwarding_path exists and is a list before appending
                if not hasattr(message, 'forwarding_path') or message.forwarding_path is None:
                    message.forwarding_path = []
                message.forwarding_path.append(
                    ForwardingPathEntry(
                        destination="backend.simulation_manager", # Using destination
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
                # Construct and send DeadLetterMessage to DLQ
                assert self._dead_letter_queue is not None, "Dead Letter Queue must be initialized."
                await self._dead_letter_queue.enqueue(DeadLetterMessage(
                    id=str(uuid.uuid4()),
                    type=ErrorTypes.UNKNOWN_MESSAGE_TYPE.value,
                    client_id=client_id,
                    payload={"original_message_data": message.model_dump(), # `payload` is now a valid field
                             "reason": ErrorTypes.UNKNOWN_MESSAGE_TYPE.value,
                             "error_details": {
                                 "type": "UnknownUniversalMessageType",
                                 "message": f"No specific handler found for UniversalMessage type: {message.type}",
                                 "component": "BackendServiceDispatcher._process_single_message",
                                 "timestamp": time.time(),
                                 "client_id": client_id,
                                 "original_universal_message_id": message.id
                             }},
                    original_message=message.model_dump(),
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
                return None # No response is generated for messages sent to DLQ here
            
            # Ensure processing_path exists and is a list before appending
            if not hasattr(message, 'processing_path') or message.processing_path is None:
                message.processing_path = []
            message.processing_path.append(
                ProcessingPathEntry(
                    processor_name="BackendServiceDispatcher", # Using processor_name
                    details={"handled_type": message.type}
                )
            )

            # Constructing UniversalMessage should now correctly accept 'payload'
            response_universal_message = UniversalMessage(
                id=f"{response_type}-{str(uuid.uuid4())}",
                type=response_type,
                client_id=client_id,
                timestamp=time.time(),
                origin="backend.dispatcher",
                destination="frontend", # Responses typically go back to frontend
                payload=response_payload, # `payload` is now a valid field
                processing_path=copy.deepcopy(message.processing_path),
                forwarding_path=copy.deepcopy(message.forwarding_path)
            )
            response_universal_message.processing_path.append(
                ProcessingPathEntry(
                    processor_name="BackendServiceDispatcher", # Using processor_name
                    details={"to_queue": "queues.outgoing"}
                )
            )
            return response_universal_message

        except ValidationError as e:
            logger.error(f"Validation error during single message processing for message {msg_id}: {e}", exc_info=True)
            dlq_client_id = client_id or 'unknown_client_error'
            # Enqueue to Dead Letter Queue for validation errors
            assert self._dead_letter_queue is not None, "Dead Letter Queue must be initialized."
            await self.safe_enqueue(self._dead_letter_queue, DeadLetterMessage(
                id=str(uuid.uuid4()),
                type=ErrorTypes.SYSTEM_ERROR.value, # Using .value
                client_id=dlq_client_id,
                payload={"original_message_data": message.model_dump(), # `payload` is now a valid field
                         "reason": ErrorTypes.VALIDATION.value, # Using .value
                         "error_details": {"validation_error": str(e), "component": "BackendServiceDispatcher._process_single_message"}},
                original_message=message.model_dump(),
                reason=ErrorTypes.VALIDATION.value, # Using .value
                error_details={"validation_error": str(e), "component": "BackendServiceDispatcher._process_single_message"}
            ))
            return None
        except Exception as e:
            logger.error(f"Critical error during single message processing for message {msg_id}: {str(e)}", exc_info=True)
            dlq_client_id = client_id or 'unknown_client_error'
            # Enqueue to Dead Letter Queue for general exceptions
            assert self._dead_letter_queue is not None, "Dead Letter Queue must be initialized."
            await self.safe_enqueue(self._dead_letter_queue, DeadLetterMessage(
                id=str(uuid.uuid4()),
                type=ErrorTypes.SYSTEM_ERROR.value, # Using .value
                client_id=dlq_client_id,
                payload={"original_message_data": message.model_dump(), # `payload` is now a valid field
                         "reason": ErrorTypes.SYSTEM_ERROR.value, # Using .value
                         "error_details": {"exception": str(e), "component": "BackendServiceDispatcher._process_single_message"}},
                original_message=message.model_dump(),
                reason=ErrorTypes.SYSTEM_ERROR.value, # Using .value
                error_details={"exception": str(e), "component": "BackendServiceDispatcher._process_single_message"}
            ))
            return None

    async def safe_enqueue(self, queue, message: Union[UniversalMessage, DeadLetterMessage]) -> bool:
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
                    pass
            if self._dlq_monitor_task: # Ensure DLQ monitor task is also stopped
                self._dlq_monitor_task.cancel()
                try:
                    await self._dlq_monitor_task
                except asyncio.CancelledError:
                    pass
            logger.info("BackendServiceDispatcher shutdown complete.")
        else:
            logger.info("BackendServiceDispatcher was not running.")