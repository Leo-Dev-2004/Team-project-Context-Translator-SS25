# Backend/MessageRouter.py

import asyncio
import logging
import time
from typing import Dict, Any, Optional
import uuid
from pydantic import ValidationError

# Import UniversalMessage and its related models
from Backend.models.UniversalMessage import (
    UniversalMessage,
    ProcessingPathEntry,
    ForwardingPathEntry, # Keep if used elsewhere, removed from this example's use.
    ErrorTypes
)

# Import the global queues instance
from Backend.core.Queues import queues
# --- CORRECTED IMPORT AND HINTING ---
# If your Queues.py hints its queue attributes as AbstractMessageQueue, use that for MessageRouter's attributes.
from Backend.queues.MessageQueue import MessageQueue # Assuming MessageQueue is a concrete class implementing the abstract one
from Backend.queues.QueueTypes import AbstractMessageQueue # NEW: Import AbstractMessageQueue if queues use it for hinting

# --- IMPORT SmallModel ---
from Backend.AI.SmallModel import SmallModel # SmallModel is now a direct processor

logger = logging.getLogger(__name__)

class MessageRouter:
    """
    The MessageRouter is responsible for routing UniversalMessages between different
    queues and services based on their 'type' and 'destination' fields.
    It acts as a central hub for message flow management.
    """

    def __init__(self):
        # --- CORRECTED: Use AbstractMessageQueue for type hints if that's what queues.py uses ---
        self._input_queue: AbstractMessageQueue = queues.incoming
        self._output_queue: AbstractMessageQueue = queues.outgoing
        self._websocket_out_queue: AbstractMessageQueue = queues.websocket_out

        self._running = False
        self._router_task: Optional[asyncio.Task] = None
        logger.info("MessageRouter initialized with global queues.")

        # --- SmallModel is a direct processor, instantiate it ---
        self._small_model: SmallModel = SmallModel()
        logger.info("SmallModel instance created in MessageRouter (as a direct processor).")


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
            message: Optional[UniversalMessage] = None
            try:
                message = await self._input_queue.dequeue()
                logger.debug(
                    f"MessageRouter received message (ID: {message.id}, Type: {message.type}, "
                    f"Origin: {message.origin}, Destination: {message.destination})."
                )

                message.processing_path.append(ProcessingPathEntry(
                    processor="MessageRouter",
                    status="received_for_routing",
                    timestamp=time.time(),
                    details=None,
                    completed_at=None # Router is still processing this message, so not completed yet
                ))

                await self._process_and_route_message(message)

            except asyncio.CancelledError:
                logger.info("MessageRouter loop cancelled.")
                break
            except Exception as e:
                logger.error(f"MessageRouter encountered unhandled error in main loop: {e}", exc_info=True)
                # Create and route an error message for unhandled exceptions in the router's main loop
                problematic_message_id = message.id if message else str(uuid.uuid4())
                error_for_frontend = UniversalMessage(
                    id=problematic_message_id,
                    type=ErrorTypes.INTERNAL_SERVER_ERROR.value, # --- CORRECTED: Use .value ---
                    payload={"error": f"Router loop unhandled exception: {e}", "original_message_id": problematic_message_id},
                    origin="MessageRouter",
                    destination="frontend",
                    client_id=message.client_id if message else None, # Keep original client_id if available
                    processing_path= (message.processing_path if message else []) + [
                        ProcessingPathEntry(
                            processor="MessageRouter",
                            status="router_loop_exception",
                            timestamp=time.time(),
                            completed_at=time.time(),
                            details={"error_message": str(e)}
                        )
                    ]
                )
                await self._websocket_out_queue.enqueue(error_for_frontend) # Send error to client
                logger.error(f"Sent error message {error_for_frontend.id} due to unhandled router loop error.")


    async def _process_and_route_message(self, message: UniversalMessage):
        """
        Processes a single message and routes it to the appropriate queue or service.
        """
        try:
            # --- CORRECTED: Direct call to SmallModel's process_message and handle its return ---
            if message.type == "stt.transcription":
                logger.debug(f"MessageRouter: Sending STT transcription (ID: {message.id}) to SmallModel for direct processing.")

                message.processing_path.append(ProcessingPathEntry(
                    processor="MessageRouter",
                    status="forwarding_to_SmallModel_direct_call",
                    timestamp=time.time(),
                    details={"action": "Direct invocation of SmallModel.process_message"},
                    completed_at=time.time() # Router's forwarding action is done here
                ))

                # Call SmallModel's processing function directly
                response_from_small_model = await self._small_model.process_message(message)

                logger.debug(f"MessageRouter: Received response from SmallModel for {message.id}. Type: {response_from_small_model.type}")

                # Now, route the response from SmallModel, typically to the frontend
                if response_from_small_model.destination == "frontend":
                    response_from_small_model.processing_path.append(ProcessingPathEntry(
                        processor="MessageRouter",
                        status="routed_to_frontend_from_small_model_response",
                        timestamp=time.time(),
                        completed_at=time.time(), # Router's part in this step is completed
                        details={"target_queue": self._websocket_out_queue.name}
                    ))
                    await self._websocket_out_queue.enqueue(response_from_small_model)
                    logger.debug(f"MessageRouter: SmallModel response {response_from_small_model.id} enqueued to websocket_out.")
                else:
                    logger.warning(
                        f"MessageRouter: SmallModel returned message (ID: {response_from_small_model.id}) "
                        f"with unhandled destination '{response_from_small_model.destination}'. "
                        "No specific route for this destination after SmallModel processing."
                    )
                    # If SmallModel's response isn't for the frontend, it might be for another backend service.
                    # You'd need more specific routing rules here. For now, assume it's for frontend
                    # or it's an unhandled case.

                return # Router's job for this message type is complete

            # --- EXISTING ROUTING LOGIC (for other message types or destinations) ---
            target_queue: Optional[AbstractMessageQueue] = None # --- CORRECTED: Hint as AbstractMessageQueue ---

            # Route based on message destination
            if message.destination == "backend.dispatcher":
                target_queue = self._output_queue
                logger.debug(f"MessageRouter: Routing message {message.id} to backend.dispatcher.")
            elif message.destination == "frontend":
                target_queue = self._websocket_out_queue
                logger.debug(f"MessageRouter: Routing message {message.id} to frontend (websocket_out).")
            else:
                logger.warning(
                    f"MessageRouter: Unknown or unroutable message destination '{message.destination}' "
                    f"and type '{message.type}' for message ID: {message.id}. No direct route found."
                )
                # Create an error message for unroutable message
                unroutable_error = UniversalMessage(
                    id=message.id,
                    type=ErrorTypes.ROUTING_ERROR.value, # --- CORRECTED: Use .value ---
                    timestamp=time.time(),
                    payload={"error": f"Message could not be routed. Unknown destination: {message.destination}", "original_message_id": message.id},
                    origin="message_router",
                    client_id=message.client_id,
                    destination="frontend", # Try to send this error back to the client
                    processing_path=message.processing_path + [
                        ProcessingPathEntry(
                            processor="MessageRouter",
                            status="unroutable_destination",
                            timestamp=time.time(),
                            completed_at=time.time(),
                            details={"destination_attempted": message.destination, "message_type": message.type}
                        )
                    ]
                )
                await self._websocket_out_queue.enqueue(unroutable_error) # Send error to frontend
                return # Stop processing this message

            if target_queue:
                message.processing_path.append(ProcessingPathEntry(
                    processor="MessageRouter",
                    status="routed_to_target_queue",
                    timestamp=time.time(),
                    completed_at=time.time(), # Router's part in this step is done
                    details={"target_queue": target_queue.name}
                ))
                await target_queue.enqueue(message)
                logger.debug(f"Message {message.id} successfully enqueued to {target_queue.name}.")
            else:
                logger.error(f"MessageRouter: Internal error, target queue unexpectedly None for message ID: {message.id}.")
                # Should be caught by the 'else' above, but good for defensive programming.

        except ValidationError as ve:
            logger.error(f"MessageRouter: Message validation error during routing for message ID: {message.id}. Error: {ve}", exc_info=True)
            validation_error_msg = UniversalMessage(
                id=message.id,
                type=ErrorTypes.VALIDATION_ERROR.value, # --- CORRECTED: Use .value ---
                timestamp=time.time(),
                payload={"error": f"Message validation failed: {ve}", "original_message_id": message.id},
                origin="message_router",
                client_id=message.client_id,
                destination="frontend",
                processing_path=message.processing_path + [
                    ProcessingPathEntry(
                        processor="MessageRouter",
                        status="message_validation_failed",
                        timestamp=time.time(),
                        completed_at=time.time(),
                        details={"validation_error": str(ve)}
                    )
                ]
            )
            await self._websocket_out_queue.enqueue(validation_error_msg)
        except Exception as e:
            logger.error(f"MessageRouter: Critical error processing and routing message ID: {message.id}. Error: {e}", exc_info=True)
            internal_error_msg = UniversalMessage(
                id=message.id,
                type=ErrorTypes.INTERNAL_SERVER_ERROR.value, # --- CORRECTED: Use .value ---
                timestamp=time.time(),
                payload={"error": f"Internal routing error: {e}", "original_message_id": message.id},
                origin="message_router",
                client_id=message.client_id,
                destination="frontend",
                processing_path=message.processing_path + [
                    ProcessingPathEntry(
                        processor="MessageRouter",
                        status="internal_routing_exception",
                        timestamp=time.time(),
                        completed_at=time.time(),
                        details={"exception_type": type(e).__name__, "error_message": str(e)}
                    )
                ]
            )
            await self._websocket_out_queue.enqueue(internal_error_msg)