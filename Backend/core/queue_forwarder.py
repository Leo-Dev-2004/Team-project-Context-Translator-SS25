import asyncio
import logging
import time
from typing import Optional, Dict, Any, Union

# Import the Pydantic message models
from Backend.models.message import QueueMessage, DeadLetterMessage, ForwardingPathEntry, WebSocketMessage # Added WebSocketMessage for potential type in ws_manager.send_message_to_client
from ..queues.shared_queue import (
    get_to_frontend_queue,   # <-- Input queue for this forwarder
    get_dead_letter_queue
)
# Assuming WebSocketManager is in Backend/services/websocket_manager.py
from Backend.services.websocket_manager import WebSocketManager # Adjust import path as needed

logger = logging.getLogger(__name__)

class QueueForwarder:
    def __init__(self, websocket_manager: WebSocketManager):
        self._running = False
        # CORRECTED INPUT QUEUE: Listen to messages *for* the frontend
        # This queue will contain QueueMessage or DeadLetterMessage Pydantic objects
        self._input_queue = get_to_frontend_queue()
        
        # The _output_queue is indeed no longer relevant for the Forwarder's role
        # as it forwards directly to WebSocketManager. Removing it for clarity.
        # self._output_queue = get_to_backend_queue() # REMOVED
        
        self._dead_letter_queue = get_dead_letter_queue()
        self._name = "WebSocketResponseForwarder" # Give it a more descriptive name
        self.ws_manager = websocket_manager # Store WebSocketManager instance

        # Validate queues and WebSocketManager
        if None in (self._input_queue, self._dead_letter_queue, self.ws_manager):
            raise RuntimeError("QueueForwarder: All dependencies (queues, WebSocketManager) must be initialized during construction")
        
        logger.info("QueueForwarder initialized with all queues and WebSocketManager.")

    async def initialize(self):
        """Confirm Queue initialization (no re-initialization needed)"""
        # This method seems to just log, assuming queues are initialized application-wide.
        try:
            logger.info("QueueForwarder queues already initialized")
        except Exception as e:
            logger.error(f"Failed to initialize QueueForwarder: {str(e)}")
            raise

    async def forward(self):
        """Forwarding loop with enhanced monitoring"""
        self._running = True
        forward_count = 0
        last_log_time = time.time()
        
        logger.info(f"Starting QueueForwarder {self._name} with input='{self._input_queue.name}' (to WebSocket).")

        while self._running:
            try:
                current_time = time.time()
                if current_time - last_log_time > 5:
                    logger.info(
                        f"QueueForwarder {self._name} stats - "
                        f"Forwarded: {forward_count}, "
                        f"Input Q ('{self._input_queue.name}'): {self._input_queue.qsize()}"
                    )
                    forward_count = 0
                    last_log_time = current_time

                # Dequeue message from the queue containing responses for the frontend
                # This will now return a Pydantic QueueMessage or DeadLetterMessage object
                message: Union[QueueMessage, DeadLetterMessage] = await self._input_queue.dequeue()
                
                # Note: Queue.dequeue() blocks until an item is available, it won't return None on empty.
                # The 'message is None' check is removed as it's no longer needed for Queue-based queues.

                # Simulate a very short processing delay before sending
                await asyncio.sleep(0.01)

                # Nachrichtenvalidierung (validate message before sending)
                # Now _validate_message expects Pydantic objects, and we pass it the object directly.
                if not self._validate_message(message):
                    logger.warning(f"Invalid message format for forwarding to WebSocket: {message}")
                    
                    dead_letter_entry_obj = DeadLetterMessage(
                        original_message=message.model_dump(), # Convert Pydantic to dict for DLQ original_message field
                        reason="Invalid message format for WebSocket forwarding",
                        error_details={
                            "type": "invalid_format",
                            "message": "Message did not pass QueueForwarder validation for WebSocket sending",
                            "component": "QueueForwarder",
                            "timestamp": time.time()
                        },
                        client_id=getattr(message, 'client_id', 'unknown') # Get client_id if available
                    )
                    await self._dead_letter_queue.enqueue(dead_letter_entry_obj) # Enqueue Pydantic DLQ object
                    continue

                # Get client_id from the message using dot notation
                client_id = message.client_id # Direct access to Pydantic attribute
                if not client_id:
                    logger.warning(f"Message {message.id or 'N/A'} has no client_id. Cannot forward via WebSocket.")
                    
                    dead_letter_entry_obj = DeadLetterMessage(
                        original_message=message.model_dump(), # Convert Pydantic to dict
                        reason="Missing client_id for WebSocket forwarding",
                        error_details={
                            "type": "missing_client_id",
                            "message": "Message could not be forwarded due to missing client_id",
                            "component": "QueueForwarder",
                            "timestamp": time.time()
                        },
                        client_id=getattr(message, 'client_id', 'unknown')
                    )
                    await self._dead_letter_queue.enqueue(dead_letter_entry_obj) # Enqueue Pydantic DLQ object
                    continue

                # DIRECTLY SEND THE MESSAGE TO THE CLIENT VIA WEBSOCKETMANAGER
                # Pass the Pydantic message object directly to send_message_to_client
                # It's assumed ws_manager.send_message_to_client expects a Pydantic object now.
                if await self.ws_manager.send_message_to_client(client_id, message):
                    forward_count += 1
                    logger.debug(f"QueueForwarder: Successfully sent message type '{message.type}' to client {client_id}.")
                else:
                    logger.warning(f"QueueForwarder: Failed to send message type '{message.type}' to client {client_id}. Sending to DLQ.")
                    
                    dead_letter_entry_obj = DeadLetterMessage(
                        original_message=message.model_dump(), # Convert Pydantic to dict
                        reason="Failed to forward message to WebSocket client",
                        error_details={
                            "type": "send_failure",
                            "message": "Failed to forward message to WebSocket client",
                            "component": "QueueForwarder",
                            "timestamp": time.time()
                        },
                        client_id=client_id
                    )
                    await self._dead_letter_queue.enqueue(dead_letter_entry_obj) # Enqueue Pydantic DLQ object

            except asyncio.CancelledError:
                logger.info("QueueForwarder task cancelled.")
                self._running = False
            except Exception as e:
                logger.error(f"Forwarding error in QueueForwarder: {e}", exc_info=True)
                await asyncio.sleep(1) # Small backoff on unexpected errors

        logger.info("QueueForwarder stopped")

    def _validate_message(self, message: Union[QueueMessage, DeadLetterMessage]) -> bool:
        """
        Validates the message structure for forwarding.
        Since we are now dealing with Pydantic objects, validation is simpler.
        We ensure it's the correct type and has essential attributes.
        """
        # The message is already a Pydantic object (QueueMessage or DeadLetterMessage)
        # from the queue. We just need to check for essential attributes if necessary.
        
        # DeadLetterMessage inherits from QueueMessage, so checking for QueueMessage covers both
        if not isinstance(message, QueueMessage): # Or just check for the Union if you want to be super explicit
             return False # Should ideally not happen if enqueued correctly

        # Check if it has required fields for sending via WebSocket
        # Pydantic models should guarantee these exist if defined as non-Optional
        if not hasattr(message, 'type') or not message.type:
            logger.warning(f"Message {message.id} missing 'type' field.")
            return False
        if not hasattr(message, 'data') or not message.data:
            logger.warning(f"Message {message.id} missing 'data' field.")
            return False
        if not hasattr(message, 'client_id') or not message.client_id:
            logger.warning(f"Message {message.id} missing 'client_id' field.")
            return False
            
        return True

    # Removed _safe_dequeue as it's no longer needed (MessageQueue.dequeue handles safety)
    # Removed _safe_enqueue as it's no longer needed (direct enqueue of Pydantic object is safe)

    async def stop(self):
        """Ordered shutdown"""
        self._running = False
        logger.debug("QueueForwarder shutdown initiated")