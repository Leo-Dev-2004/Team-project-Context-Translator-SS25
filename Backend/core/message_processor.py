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

    async def process(self):
        """Process messages through the full pipeline"""
        logger.info("Starting message processor")
        while True:
            try:
                backend_msg = await self._to_backend_queue.dequeue()
                
                try:
                    validated_msg = QueueMessage(**backend_msg)
                    backend_msg = validated_msg.dict()
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
