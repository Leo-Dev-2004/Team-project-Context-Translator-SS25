import asyncio
import logging
import time
from typing import Optional, Dict, Any, Union

# Import the Pydantic message models
from Backend.models.message_types import QueueMessage, DeadLetterMessage, ForwardingPathEntry, WebSocketMessage, SystemMessage

from Backend.services.websocket_manager import WebSocketManager
from Backend.core.Queues import queues

logger = logging.getLogger(__name__)

class QueueForwarder:
    def __init__(self, websocket_manager: WebSocketManager):
        self._running = False
        self._input_queue = queues.to_frontend # This queue feeds messages *to* the frontend
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

    async def forward(self):
        self._running = True
        logger.info("QueueForwarder starting to listen for messages from 'to_frontend' queue.")
        while self._running:
            message: Optional[QueueMessage] = None # Initialize message to None
            try:
                assert queues.to_frontend is not None, "to_frontend queue not initialized for QueueForwarder!"
                message = await queues.to_frontend.dequeue()
                assert message is not None, "Dequeued message is None! This should not happen if the queue is properly populated."
                logger.debug(f"QueueForwarder dequeued message ID: {message.id}, Type: {message.type}")

                # Add the current processor to the forwarding path
                message.forwarding_path.append(
                    ForwardingPathEntry(
                        processor=self._name, # or a more specific identifier like "QueueForwarder_dequeued"
                        status="dequeued",
                        from_queue="to_frontend" # Assuming this is the queue it came from
                    )
                )

                # --- NEW HANDLING FOR PONG AND BACKEND_READY_CONFIRM ---
                if message.type == "pong":
                    logger.debug(f"QueueForwarder sending pong to client {message.client_id}.")
                    if message.client_id and self.ws_manager:
                        message.forwarding_path.append(
                            ForwardingPathEntry(
                                processor=self._name,
                                status="sent_pong_to_websocket",
                                to_queue=None # Directly to WebSocket
                            )
                        )
                        await self.ws_manager.send_message_to_client(message.client_id, message)
                        logger.debug(f"QueueForwarder successfully sent pong for client {message.client_id}.")
                    else:
                        logger.warning(f"Pong message ID {message.id} missing client_id or ws_manager. Sending to DLQ.")
                        assert queues.dead_letter is not None, "Pong message must have a client_id or WebSocketManager"
                        await queues.dead_letter.enqueue(DeadLetterMessage(
                            original_message=message.model_dump(),
                            reason="Pong message missing client_id or WebSocketManager.",
                            client_id=message.client_id
                        ))
                elif message.type == "backend_ready_confirm":
                    # This message type is intended for the frontend.
                    # It confirms the backend is ready after a frontend_ready_ack.
                    logger.info(f"QueueForwarder forwarding backend_ready_confirm to client {message.client_id}.")
                    if message.client_id and self.ws_manager:
                        # Append to forwarding path for sending to WS
                        message.forwarding_path.append(
                            ForwardingPathEntry(
                                processor=self._name,
                                status="forwarding_to_websocket",
                                to_queue=None # No queue, directly to WebSocket
                            )
                        )
                        await self.ws_manager.send_message_to_client(message.client_id, message)
                        logger.debug(f"QueueForwarder sent backend_ready_confirm ID {message.id} to client {message.client_id}.")
                    else:
                        assert queues.dead_letter is not None, "backend_ready_confirm message must have a client_id"
                        logger.warning(f"Backend_ready_confirm ID {message.id} missing client_id or ws_manager. Sending to DLQ.")
                        await queues.dead_letter.enqueue(DeadLetterMessage(
                            original_message=message.model_dump(),
                            reason="backend_ready_confirm missing client_id or WebSocketManager.",
                            client_id=message.client_id
                        ))
                # --- END NEW HANDLING ---

                elif message.type == "websocket_message":
                    if message.client_id and self.ws_manager:
                        # Append to forwarding path for sending to WS
                        message.forwarding_path.append(
                            ForwardingPathEntry(
                                processor=self._name,
                                status="forwarding_to_websocket",
                                to_queue=None # No queue, directly to WebSocket
                            )
                        )
                        await self.ws_manager.send_message_to_client(message.client_id, message)
                        logger.debug(f"QueueForwarder forwarded message ID {message.id} to client {message.client_id}.")
                    else:
                        assert queues.dead_letter is not None, "websocket_message must have a client_id"
                        logger.warning(f"Message ID {message.id} is a websocket_message but has no client_id or websocket_manager is not set. Sending to DLQ.")
                        await queues.dead_letter.enqueue(DeadLetterMessage(
                            original_message=message.model_dump(),
                            reason="Websocket message with no client_id or no manager.",
                            client_id=message.client_id
                        ))
                elif message.type == "simulation_data":
                    logger.debug(f"QueueForwarder received simulation_data: {message.data}")
                    if self.ws_manager:
                        # Append to forwarding path for sending to WS (to multiple clients)
                        message.forwarding_path.append(
                            ForwardingPathEntry(
                                processor=self._name,
                                status="broadcasting_to_websockets",
                                to_queue=None # No queue, directly to WebSocket
                            )
                        )
                        for client_id in self.ws_manager.connections.keys():
                            await self.ws_manager.send_message_to_client(client_id, message)
                            logger.debug(f"QueueForwarder forwarded simulation_data to client {client_id}.")
                elif message.type == "queue_status":
                     # This is a backend-generated status message intended for the frontend
                     logger.debug(f"QueueForwarder forwarding queue_status to clients.")
                     if self.ws_manager:
                        message.forwarding_path.append(
                            ForwardingPathEntry(
                                processor=self._name,
                                status="broadcasting_queue_status",
                                to_queue=None
                            )
                        )
                        for client_id in self.ws_manager.connections.keys():
                            await self.ws_manager.send_message_to_client(client_id, message)
                            logger.debug(f"QueueForwarder forwarded queue_status to client {client_id}.")
                else:
                    unhandled_msg = f"QueueForwarder received unhandled message type: {message.type}. Message ID: {message.id}"
                    logger.warning(unhandled_msg)
                    assert queues.dead_letter is not None, "Unhandled message must be sent to dead letter queue"    
                    await queues.dead_letter.enqueue(DeadLetterMessage(
                        original_message=message.model_dump(),
                        reason=unhandled_msg,
                        client_id=message.client_id
                    ))

            except asyncio.CancelledError:
                logger.info("QueueForwarder task cancelled.")
                break
            except Exception as e:
                logger.error(f"Error in QueueForwarder during message processing: {e}", exc_info=True)
                if message is not None:
                    try:
                        assert queues.dead_letter is not None, "Dead letter queue must be initialized for error handling"
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
                await asyncio.sleep(1)
        logger.info("QueueForwarder loop ended.")


    # Removed _send_to_dead_letter_queue as it's now handled inline where needed.
    # If you still have calls to this from other parts of QueueForwarder, you'll need to adapt them.
    # For now, it's safer to remove if not directly used, to avoid confusion.

    def _validate_message(self, message: Union[QueueMessage, DeadLetterMessage]) -> bool:
        """
        Validates the message structure for forwarding.
        This now checks that a QueueMessage or DeadLetterMessage is received,
        and that it has a client_id and a type, which are crucial for WebSocket sending.
        The 'data' field is now optional for this validation, as some messages (like pong)
        might have empty or minimal data.
        """
        # This method is not currently called in the 'forward' loop, but if it were:
        if not isinstance(message, (QueueMessage, DeadLetterMessage)):
            logger.warning(f"Received non-QueueMessage/DeadLetterMessage type: {type(message).__name__}.")
            return False

        if not getattr(message, 'type', None):
            logger.warning(f"Message {getattr(message, 'id', 'N/A')} missing 'type' field.")
            return False

        # As noted, 'client_id' check is handled downstream before sending.
        # So we don't return False here for missing client_id.
        if not getattr(message, 'data', None):
            logger.debug(f"Message {getattr(message, 'id', 'N/A')} has empty 'data' field. (Normal for pong/ack)")

        return True

    async def stop(self):
        self._running = False
        logger.debug("QueueForwarder shutdown initiated")