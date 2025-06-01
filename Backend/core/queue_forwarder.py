import asyncio
import logging
import time
from typing import Optional, Dict, Any # Added Any for WebSocketManager
from ..queues.shared_queue import (
    get_from_frontend_queue, # No longer needed here
    get_to_backend_queue,    # No longer needed here
    get_to_frontend_queue,   # <-- NEW: This is the input queue
    get_dead_letter_queue
)
# Assuming WebSocketManager is in core/websocket_manager.py or similar
from Backend.services.websocket_manager import WebSocketManager # Adjust import path as needed

logger = logging.getLogger(__name__)

class QueueForwarder:
    # Accept WebSocketManager in constructor
    def __init__(self, websocket_manager: WebSocketManager):
        self._running = False
        # CORRECTED INPUT QUEUE: Listen to messages *for* the frontend
        self._input_queue = get_to_frontend_queue()
        # The output_queue is no longer relevant for the Forwarder's role
        # It's forwarding directly to WebSocketManager, not another queue.
        # So, you can remove _output_queue or keep it for debugging/future use,
        # but it won't be used in the forward loop. Let's remove it for clarity.
        # self._output_queue = get_to_backend_queue() # REMOVE OR RENAME IF NOT USED
        self._dead_letter_queue = get_dead_letter_queue()
        self._name = "WebSocketResponseForwarder" # Give it a more descriptive name
        self.ws_manager = websocket_manager # Store WebSocketManager instance

        # Validate queues and WebSocketManager
        if None in (self._input_queue, self._dead_letter_queue, self.ws_manager):
            raise RuntimeError("QueueForwarder: All dependencies (queues, WebSocketManager) must be initialized during construction")
        
        logger.info("QueueForwarder initialized with all queues and WebSocketManager.")

    async def initialize(self):
        """Confirm Queue initialization (no re-initialization needed)"""
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
        
        # Adjust logging to reflect actual input/output
        logger.info(f"Starting QueueForwarder {self._name} with input={self._input_queue._name} (to WebSocket).")

        while self._running:
            try:
                current_time = time.time()
                if current_time - last_log_time > 5:
                    logger.info(
                        f"QueueForwarder {self._name} stats - "
                        f"Forwarded: {forward_count}, "
                        f"Input Q ({self._input_queue._name}): {self._input_queue.size()}"
                        # Removed output queue from logs as it's not directly used for forwarding
                    )
                    forward_count = 0
                    last_log_time = current_time

                # Dequeue message from the queue containing responses for the frontend
                message = await self._input_queue.dequeue()
                
                if message is None:
                    await asyncio.sleep(0.01) # Small sleep to prevent busy-wait
                    continue

                # Simulate a very short processing delay before sending
                await asyncio.sleep(0.01)

                # Nachrichtenvalidierung (validate message before sending)
                if not self._validate_message(message):
                    logger.warning(f"Invalid message format for forwarding to WebSocket: {message}")
                    await self._safe_enqueue(self._dead_letter_queue, {
                        'original_message': message,
                        'error': 'invalid_format_for_websocket_forwarding',
                        'timestamp': time.time()
                    })
                    continue

                # Get client_id from the message to know where to send it
                client_id = message.get("client_id")
                if not client_id:
                    logger.warning(f"Message {message.get('id', 'N/A')} has no client_id. Cannot forward via WebSocket.")
                    dead_letter_entry = {
                        "original_message": message,
                        "error_details": {
                            "type": "missing_client_id",
                            "message": "Message could not be forwarded due to missing client_id",
                            "component": "QueueForwarder"
                        },
                        "timestamp": time.time(),
                        "reason": "Missing client ID for forwarding"
                    }
                    await self._safe_enqueue(self._dead_letter_queue, dead_letter_entry)
                    continue

                # DIRECTLY SEND THE MESSAGE TO THE CLIENT VIA WEBSOCKETMANAGER
                # This is the key change for sending to the frontend
                if await self.ws_manager.send_message_to_client(client_id, message):
                    forward_count += 1
                    logger.debug(f"QueueForwarder: Successfully sent message type '{message.get('type')}' to client {client_id}.")
                else:
                    logger.warning(f"QueueForwarder: Failed to send message type '{message.get('type')}' to client {client_id}. Sending to DLQ.")
                    dead_letter_entry = {
                        "original_message": message,
                        "error_details": {
                            "type": "send_failure",
                            "message": "Failed to forward message to WebSocket client",
                            "component": "QueueForwarder"
                        },
                        "timestamp": time.time(),
                        "client_id": client_id,
                        "reason": "WebSocket forwarding failed"
                    }
                    await self._safe_enqueue(self._dead_letter_queue, dead_letter_entry)

            except asyncio.CancelledError:
                logger.info("QueueForwarder task cancelled.")
                self._running = False
            except Exception as e:
                logger.error(f"Forwarding error in QueueForwarder: {e}", exc_info=True)
                await asyncio.sleep(1)

        logger.info("QueueForwarder stopped")

    def _validate_message(self, message: Dict) -> bool:

        """Validierung der Nachrichtenstruktur"""

        try:

            return isinstance(message, dict) and 'type' in message and 'data' in message

        except Exception:

            return False



    async def _safe_dequeue(self, queue) -> Optional[Dict]:

        """Thread-sicheres Dequeue mit Error-Handling"""

        try:

            return await queue.dequeue() if queue else None

        except Exception as e:

            logger.warning(f"Dequeue failed: {str(e)}")

            return None



    async def _safe_enqueue(self, queue, message) -> bool:

        """Thread-sicheres Enqueue mit Error-Handling"""

        try:

            if queue:

                await queue.enqueue(message)

                return True

            return False

        except Exception as e:

            logger.warning(f"Enqueue failed: {str(e)}")

            return False



    async def stop(self):

        """Geordnetes Herunterfahren"""

        self._running = False

        logger.debug("QueueForwarder shutdown initiated")
