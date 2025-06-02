import asyncio
import logging
import time
from typing import Optional, Dict, Any, Union

# Import the Pydantic message models
from Backend.models.message_types import QueueMessage, DeadLetterMessage, ForwardingPathEntry, WebSocketMessage

from Backend.services.websocket_manager import WebSocketManager
from Backend.core.Queues import queues

logger = logging.getLogger(__name__)

class QueueForwarder:
    def __init__(self, websocket_manager: WebSocketManager):
        self._running = False
        self._input_queue = queues.to_frontend
        self._dead_letter_queue = queues.dead_letter
        self._name = "WebSocketResponseForwarder"
        self.ws_manager = websocket_manager

        if None in (self._input_queue, self._dead_letter_queue, self.ws_manager):
            raise RuntimeError("QueueForwarder: All dependencies (queues, WebSocketManager) must be initialized during construction")

        logger.info("QueueForwarder initialized with all queues and WebSocketManager.")

    async def initialize(self):
        try:
            logger.info("QueueForwarder queues already initialized")
        except Exception as e:
            logger.error(f"Failed to initialize QueueForwarder: {str(e)}")
            raise

    # <--- MODIFIED: No 'message' parameter here for a continuous loop! --->
    async def forward(self):
        self._running = True
        logger.info("QueueForwarder starting to listen for messages from 'to_frontend' queue.")
        while self._running:
            # Initialize message to None at the start of each loop iteration.
            # This ensures 'message' is always defined in the scope,
            # even if dequeueing fails.
            message: Optional[QueueMessage] = None
            try:
                # Ensure the queue is initialized before attempting to dequeue
                # Pylance will be happy if `initialize_and_assert_shared_queues()` has run
                assert queues.to_frontend is not None, "to_frontend queue not initialized for QueueForwarder!"

                # This is the queue where QueueForwarder expects messages from
                message = await queues.to_frontend.dequeue()
                assert message is not None, "Dequeued message is None! This should not happen if the queue is properly populated."
                logger.debug(f"QueueForwarder dequeued message ID: {message.id}, Type: {message.type}")

                # Now, process or forward the dequeued message
                if message.type == "websocket_message": # Example type check
                    if message.client_id and self.ws_manager:
                        await self.ws_manager.send_message_to_client(message.client_id, message)
                        logger.debug(f"QueueForwarder forwarded message ID {message.id} to client {message.client_id}.")
                    else:
                        logger.warning(f"Message ID {message.id} is a websocket_message but has no client_id or websocket_manager is not set.")
                        # Send to dead letter queue if a client_id is missing for a websocket message
                        assert queues.dead_letter is not None, "Dead letter queue not initialized!"
                        await queues.dead_letter.enqueue(DeadLetterMessage(
                            original_message=message.model_dump(),
                            reason="Websocket message with no client_id or no manager.",
                            client_id=message.client_id
                        ))
                elif message.type == "simulation_data": # Example for other types
                    logger.debug(f"QueueForwarder received simulation_data: {message.data}")
                    # You might need to send this to all clients, or a specific subset
                    if self.ws_manager:
                        for client_id in self.ws_manager.connections.keys(): # Send to all connected clients
                            await self.ws_manager.send_message_to_client(client_id, message)
                            logger.debug(f"QueueForwarder forwarded simulation_data to client {client_id}.")
                else:
                    unhandled_msg = f"QueueForwarder received unhandled message type: {message.type}. Message ID: {message.id}"
                    logger.warning(unhandled_msg)
                    # Send unhandled messages to dead letter queue
                    assert queues.dead_letter is not None, "Dead letter queue not initialized!"
                    await queues.dead_letter.enqueue(DeadLetterMessage(
                        original_message=message.model_dump(),
                        reason=unhandled_msg,
                        client_id=message.client_id
                    ))

            except asyncio.CancelledError:
                logger.info("QueueForwarder task cancelled.")
                break # Exit the loop cleanly on cancellation
            except Exception as e:
                logger.error(f"Error in QueueForwarder during message processing: {e}", exc_info=True)
                # Potentially send the problematic message to the dead letter queue if retrieval itself didn't fail
                # Or handle a retry mechanism
                # Example: If 'message' is available from a previous successful dequeue before the error,
                # you can send it to DLQ. Otherwise, log the raw error.
                if 'message' in locals(): # Check if message variable exists from successful dequeue
                    assert queues.dead_letter is not None, "Dead letter queue not initialized!"
                    assert isinstance(message, QueueMessage), "Expected message to be of type QueueMessage"
                    try:
                        await queues.dead_letter.enqueue(DeadLetterMessage(
                            original_message=message.model_dump(),
                            reason=f"Processing error in QueueForwarder: {e}",
                            client_id=message.client_id
                        ))
                        logger.error(f"Problematic message ID {message.id} sent to Dead Letter Queue.")
                    except Exception as dlq_e:
                        logger.critical(f"Failed to send problematic message to DLQ: {dlq_e}. Original error: {e}")
                        logger.critical(f"Original message: {message.model_dump()}")
                else:
                    logger.critical("Error occurred before message was successfully dequeued or assigned.")
                await asyncio.sleep(1) # Prevent busy-looping on repeated errors
        logger.info("QueueForwarder loop ended.")


    async def _send_to_dead_letter_queue(self, original_message: dict, reason: str):
        """Helper to send a message to the dead letter queue (called by other parts of QueueForwarder)."""
        logging.critical(f"Attempting to send message to Dead Letter Queue. Reason: {reason}. Original message type: {type(original_message)}")
        try:
            dl_message = DeadLetterMessage(
                type="dead_letter_entry",
                timestamp=time.time(),
                original_message=original_message,
                reason=reason,
                client_id=original_message.get('client_id') # Safely get client_id from the dict
            )
            assert queues.dead_letter is not None, "Dead letter queue not initialized!"
            await queues.dead_letter.enqueue(dl_message)
            logging.error(f"Message sent to Dead Letter Queue: {dl_message.id}")
        except Exception as e:
            logging.critical(f"Failed to send message to Dead Letter Queue directly from _send_to_dead_letter_queue: {e}. Original: {original_message}")

    def _validate_message(self, message: Union[QueueMessage, DeadLetterMessage]) -> bool:
        """
        Validates the message structure for forwarding.
        This now checks that a QueueMessage or DeadLetterMessage is received,
        and that it has a client_id and a type, which are crucial for WebSocket sending.
        The 'data' field is now optional for this validation, as some messages (like pong)
        might have empty or minimal data.
        """
        if not isinstance(message, (QueueMessage, DeadLetterMessage)):
            logger.warning(f"Received non-QueueMessage/DeadLetterMessage type: {type(message).__name__}.")
            return False

        # Essential attributes for sending via WebSocket
        # Pydantic models should guarantee 'type' and 'id' exist.
        if not getattr(message, 'type', None):
            logger.warning(f"Message {getattr(message, 'id', 'N/A')} missing 'type' field.")
            return False

        # IMPORTANT: 'client_id' is now handled by a separate check *after* validation and *before* sending.
        # So we don't need to return False here for missing client_id, just log a warning if data is missing.
        if not getattr(message, 'data', None):
            logger.debug(f"Message {getattr(message, 'id', 'N/A')} has empty 'data' field. (Normal for pong/ack)")
            # It's okay if data is empty for some message types like 'pong', 'ack'.
            # We don't return False here, as the message might still be valid.

        return True

    async def stop(self):
        self._running = False
        logger.debug("QueueForwarder shutdown initiated")