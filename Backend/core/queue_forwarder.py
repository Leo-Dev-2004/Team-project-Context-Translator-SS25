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
        self._input_queue = None
        self._output_queue = None
        self._dead_letter_queue = None

    async def initialize(self):
        """Sichere Initialisierung mit Queue-Validierung"""
        try:
            self._input_queue = get_from_frontend_queue()
            self._output_queue = get_to_backend_queue()
            self._dead_letter_queue = get_dead_letter_queue()

            if None in (self._input_queue, self._output_queue, self._dead_letter_queue):
                raise RuntimeError("One or more queues not initialized")

            logger.info("QueueForwarder queues verified")
        except Exception as e:
            logger.error(f"Failed to initialize QueueForwarder: {str(e)}")
            raise

    async def forward(self):
        """Hauptweiterleitungsschleife mit robustem Error-Handling"""
        self._running = True
        logger.info("Starting QueueForwarder")

        while self._running:
            try:
                # Nachricht empfangen
                message = await self._safe_dequeue(self._input_queue)
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
                
                # Add current forwarding step
                message['forwarding_path'].append(f'queue_forwarder:{self._input_queue._name}->{self._output_queue._name}')

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
