import asyncio
import logging
import time
from ..queues.shared_queue import MessageQueue

logger = logging.getLogger(__name__)

class QueueForwarder:
    def __init__(
        self,
        from_backend_queue: MessageQueue,
        to_frontend_queue: MessageQueue,
        from_frontend_queue: MessageQueue,
        to_backend_queue: MessageQueue
    ):
        self._from_backend_queue = from_backend_queue
        self._to_frontend_queue = to_frontend_queue
        self._from_frontend_queue = from_frontend_queue
        self._to_backend_queue = to_backend_queue

    async def forward(self):
        """Forward messages between queues"""
        logger.info("Starting queue forwarder")
        while True:
            try:
                # Forward from backend to frontend
                backend_msg = await self._from_backend_queue.dequeue()
                if backend_msg and isinstance(backend_msg, dict):
                    try:
                        if not isinstance(backend_msg.get('data'), dict):
                            backend_msg['data'] = {}
                        
                        backend_msg.setdefault('forwarding_path', [])
                        backend_msg['forwarding_path'].append({
                            'from': 'from_backend_queue',
                            'to': 'to_frontend_queue',
                            'timestamp': time.time()
                        })
                        
                        msg_id = backend_msg.get('data', {}).get('id', 'unknown_id')
                        logger.debug(f"Forwarding message {msg_id} to frontend")
                        
                        # Ensure message has required fields for frontend
                        frontend_msg = {
                            'type': backend_msg.get('type', 'unknown'),
                            'data': backend_msg.get('data', {}),
                            'timestamp': time.time()
                        }
                        
                        await self._to_frontend_queue.enqueue(frontend_msg)
                        logger.info(f"Successfully forwarded message {msg_id} to frontend")
                        
                    except Exception as e:
                        logger.error(f"Error forwarding message: {e}")

                # Forward from frontend to backend
                frontend_msg = await self._from_frontend_queue.dequeue()
                if frontend_msg and isinstance(frontend_msg, dict):
                    if not isinstance(frontend_msg.get('data'), dict):
                        frontend_msg['data'] = {}
                    
                    frontend_msg['status'] = 'new_for_backend'
                    msg_id = frontend_msg.get('data', {}).get('id', 'unknown_id')
                    await self._to_backend_queue.enqueue(frontend_msg)
                    logger.debug(f"Forwarded frontend message {msg_id} to backend")

                await asyncio.sleep(0.1)
            except Exception as e:
                logger.error(f"Error in queue forwarding: {e}")
                await asyncio.sleep(1)
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

                # Nachricht weiterleiten oder an Dead-Letter-Queue
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
