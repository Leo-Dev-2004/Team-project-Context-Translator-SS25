import asyncio
import logging
import time
from typing import Dict
from ..models.message_types import BackendProcessedMessage
from ..queues.shared_queue import to_backend_queue, from_backend_queue, to_frontend_queue

logger = logging.getLogger(__name__)

async def process_messages():
    """Process messages through the full pipeline with blocking behavior"""
    from ..queues.shared_queue import to_backend_queue, from_backend_queue, to_frontend_queue
    
    logger.info("Starting message processor...")
    while True:
        try:
            # Ensure queue is initialized
            if to_backend_queue is None:
                logger.error("to_backend_queue not initialized!")
                await asyncio.sleep(1)
                continue
                
            # Block until we get a message from to_backend_queue
            backend_msg = await to_backend_queue.dequeue()
            
            # Process message and send to from_backend_queue
            processed_msg = BackendProcessedMessage(
                type="processed",
                data=backend_msg.get("data", {}),
                status="processed"
            )
            await from_backend_queue.enqueue(processed_msg.dict())
            
            # Create frontend message
            frontend_msg = {
                'type': 'frontend_update',
                'data': processed_msg.dict(),
                'timestamp': time.time()
            }
            await to_frontend_queue.enqueue(frontend_msg)
            
            logger.info(f"Processed message: {backend_msg.get('data', {}).get('id')}")
                
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            await asyncio.sleep(1)
