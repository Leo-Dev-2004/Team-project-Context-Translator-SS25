import asyncio
import logging
import time
from typing import Dict
from pydantic import ValidationError
from ..models.message_types import QueueMessage
from ..queues.shared_queue import MessageQueue

logger = logging.getLogger(__name__)

class MessageProcessor:
    def __init__(
        self,
        to_backend_queue: MessageQueue,
        from_backend_queue: MessageQueue,
        to_frontend_queue: MessageQueue
    ):
        self._to_backend_queue = to_backend_queue
        self._from_backend_queue = from_backend_queue
        self._to_frontend_queue = to_frontend_queue

    async def process_pipeline(self):
        """Process messages through the full pipeline"""
        logger.info("Starting message processor")
        while True:
            try:
                raw_msg = await self._to_backend_queue.dequeue()
                
                try:
                    # Ensure message has required fields
                    if not isinstance(raw_msg, dict):
                        raise ValidationError("Message must be a dictionary")
                    if 'data' not in raw_msg:
                        raw_msg['data'] = {}
                    
                    msg = QueueMessage(**raw_msg)
                    backend_msg = msg.dict()
                except ValidationError as e:
                    logger.error(f"Invalid message format: {e}")
                    continue
                    
                if not backend_msg:
                    logger.warning("Received None message")
                    continue
                
                backend_msg.setdefault('processing_path', [])
                backend_msg['processing_path'].append({
                    'stage': 'processing_start',
                    'timestamp': time.time()
                })
                
                backend_msg['status'] = 'processed'
                backend_msg['processing_path'].append({
                    'stage': 'processing_complete',
                    'timestamp': time.time()
                })
                
                await self._from_backend_queue.enqueue(backend_msg)
                
                frontend_msg = {
                    'type': 'frontend_update',
                    'data': backend_msg,
                    'timestamp': time.time()
                }
                await self._to_frontend_queue.enqueue(frontend_msg)
                
                logger.debug(f"Processed message: {backend_msg['data']['id']}")
                
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                await asyncio.sleep(1)
    async def process(self):
        """Process messages through the full pipeline"""
        logger.info("Starting message processor")
        while True:
            try:
                # Dequeue and validate message
                raw_msg = await self._to_backend_queue.dequeue()
                try:
                    msg = QueueMessage(**raw_msg)
                except ValidationError as e:
                    logger.error(f"Invalid message format: {e}")
                    continue

                # Track processing path
                if not msg.processing_path:
                    msg.processing_path = []
                msg.processing_path.append({
                    'stage': 'processor',
                    'timestamp': time.time(),
                    'status': 'processing'
                })

                # Process message content
                if msg.type == 'simulation':
                    msg.data['status'] = 'processed'
                    msg.data['progress'] = 100
                elif msg.type == 'system':
                    msg.data['status'] = 'completed'

                # Forward to next queue
                await self._from_backend_queue.enqueue(msg.dict())

                # Create frontend notification
                if msg.type in ['simulation', 'system']:
                    frontend_msg = QueueMessage(
                        type='status_update',
                        data={
                            'original_id': msg.data.get('id'),
                            'status': msg.data['status'],
                            'progress': msg.data.get('progress', 0)
                        },
                        timestamp=time.time()
                    )
                    await self._to_frontend_queue.enqueue(frontend_msg.dict())

            except Exception as e:
                logger.error(f"Processing error: {e}")
                await asyncio.sleep(1)  # Prevent tight error loop
import asyncio
import logging
import time
from typing import Optional, Dict
from ..queues.shared_queue import (
    get_to_backend_queue,
    get_from_backend_queue,
    get_to_frontend_queue
)

logger = logging.getLogger(__name__)

class MessageProcessor:
    def __init__(self):
        self._running = False
        self._input_queue = None
        self._output_queue = None
        self._frontend_queue = None

    async def initialize(self):
        """Sichere Initialisierung mit Queue-Validierung"""
        try:
            self._input_queue = get_to_backend_queue()
            self._output_queue = get_from_backend_queue()
            self._frontend_queue = get_to_frontend_queue()

            if None in (self._input_queue, self._output_queue, self._frontend_queue):
                raise RuntimeError("One or more queues not initialized")

            logger.info("MessageProcessor queues verified")
        except Exception as e:
            logger.error(f"Failed to initialize MessageProcessor: {str(e)}")
            raise

    async def process(self):
        """Hauptverarbeitungsschleife mit robustem Error-Handling"""
        self._running = True
        logger.info("Starting MessageProcessor")

        while self._running:
            try:
                # Sicherer Dequeue mit Timeout
                message = await self._safe_dequeue(self._input_queue)
                if message is None:
                    await asyncio.sleep(0.1)
                    continue

                # Nachrichtenverarbeitung
                processed_msg = await self._process_message(message)
                if processed_msg:
                    # Weiterleitung an Backend und Frontend
                    await self._safe_enqueue(self._output_queue, processed_msg)
                    await self._safe_enqueue(self._frontend_queue, {
                        'type': 'status_update',
                        'data': processed_msg,
                        'timestamp': time.time()
                    })

            except Exception as e:
                logger.error(f"Processing error: {str(e)}")
                await asyncio.sleep(1)  # Backoff bei Fehlern

        logger.info("MessageProcessor stopped")

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

    async def _process_message(self, message: Dict) -> Optional[Dict]:
        """Nachrichtenverarbeitungslogik"""
        try:
            # Ihre Verarbeitungslogik hier
            if not isinstance(message, dict):
                raise ValueError("Invalid message format")
                
            message['status'] = 'processed'
            message['processed_at'] = time.time()
            return message
        except Exception as e:
            logger.error(f"Message processing failed: {str(e)}")
            return None

    async def stop(self):
        """Geordnetes Herunterfahren"""
        self._running = False
        logger.debug("MessageProcessor shutdown initiated")
