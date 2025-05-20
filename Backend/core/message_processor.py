import asyncio
import logging
from typing import Dict
from pydantic import ValidationError
from ..models.message_types import QueueMessage
from ..queues.shared_queue import (
    get_to_backend_queue,
    get_from_backend_queue,
    get_to_frontend_queue
)

logger = logging.getLogger(__name__)

class MessageProcessor:
    def __init__(self):
        self.to_backend_queue = get_to_backend_queue()
        self.from_backend_queue = get_from_backend_queue()
        self.to_frontend_queue = get_to_frontend_queue()

    async def process(self):
        """Process messages through the full pipeline"""
        logger.info("Starting message processor")
        while True:
            try:
                backend_msg = await self.to_backend_queue.dequeue()
                
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
                
                await self.from_backend_queue.enqueue(backend_msg)
                
                frontend_msg = {
                    'type': 'frontend_update',
                    'data': backend_msg,
                    'timestamp': time.time()
                }
                await self.to_frontend_queue.enqueue(frontend_msg)
                
                logger.debug(f"Processed message: {backend_msg['data']['id']}")
                
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                await asyncio.sleep(1)
