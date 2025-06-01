import asyncio
import logging
import time
from typing import Optional, Dict
from ..queues.shared_queue import (
    get_from_frontend_queue,
    get_to_backend_queue,
    get_dead_letter_queue
)

logger = logging.getLogger(__name__)

class QueueForwarder:
    def __init__(self):
        self._running = False
        # Initialisiere Queues direkt im Konstruktor
        self._input_queue = get_from_frontend_queue()
        self._output_queue = get_to_backend_queue()
        self._dead_letter_queue = get_dead_letter_queue()

        # Validiere Queues sofort
        if None in (self._input_queue, self._output_queue, self._dead_letter_queue):
            raise RuntimeError("Queues must be initialized during construction")
        
        logger.info("QueueForwarder initialized with all queues")

    async def initialize(self):
        """Bestätigt die Queue-Initialisierung (keine erneute Initialisierung mehr nötig)"""
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
        
        logger.info(f"Starting QueueForwarder {self._name} with input={self._input_queue._name}, output={self._output_queue._name}")

        while self._running:
            # Log throughput every 5 seconds
            current_time = time.time()
            if current_time - last_log_time > 5:
                logger.info(
                    f"QueueForwarder {self._name} stats - "
                    f"Forwarded: {forward_count}, "
                    f"Input Q: {self._input_queue.size()}, "
                    f"Output Q: {self._output_queue.size()}"
                )
                forward_count = 0
                last_log_time = current_time

        while self._running:
            try:
                # Nachricht empfangen - keine None-Checks mehr nötig, da Queues garantiert initialisiert
                message = await self._input_queue.dequeue()
                
                
                # Added delay
                await asyncio.sleep(1)  # Simulate processing delay
                ###


                if message is None:
                    await asyncio.sleep(0.1)
                    continue

                # Nachrichtenvalidierung
                if not self._validate_message(message):
                    logger.warning(f"Invalid message format: {message}")
                    continue

                # Ensure forwarding_path exists and is a list
                if 'forwarding_path' not in message or not isinstance(message['forwarding_path'], list):
                    message['forwarding_path'] = []
                
                # Add current forwarding step using ForwardingPathEntry
                message['forwarding_path'].append({
                    'processor': 'queue_forwarder',
                    'timestamp': time.time(),
                    'status': 'forwarded',
                    'from_queue': self._input_queue._name,
                    'to_queue': self._output_queue._name
                })

                # Forward message or send to dead letter queue
                if not await self._safe_enqueue(self._output_queue, message):
                    logger.warning("Message forwarding failed, sending to dead letter queue")
                    await self._safe_enqueue(self._dead_letter_queue, {
                        'original_message': message,
                        'error': 'forwarding_failed',
                        'timestamp': time.time()
                    })

            except Exception as e:
                logger.error(f"Forwarding error: {str(e)}")
                await asyncio.sleep(1)  # Backoff bei Fehlern

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
