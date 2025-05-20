import asyncio
import logging
from ..queues.shared_queue import from_backend_queue, to_frontend_queue, from_frontend_queue, to_backend_queue

logger = logging.getLogger(__name__)

async def forward_messages():
    """Forward messages between queues with blocking behavior"""
    from ..queues.shared_queue import from_backend_queue, to_frontend_queue, from_frontend_queue, to_backend_queue
    
    logger.info("Starting queue forwarder...")
    while True:
        try:
            # Ensure queues are initialized
            if None in [from_backend_queue, to_frontend_queue, from_frontend_queue, to_backend_queue]:
                logger.error("Queues not initialized!")
                await asyncio.sleep(1)
                continue
                
            # Forward from_backend_queue -> to_frontend_queue
            msg = await from_backend_queue.dequeue()
            if msg:
                await to_frontend_queue.enqueue(msg)
                logger.debug(f"Forwarded message {msg.get('data', {}).get('id')} to frontend")

            # Forward from_frontend_queue -> to_backend_queue
            frontend_msg = await from_frontend_queue.dequeue()
            if frontend_msg:
                frontend_msg['status'] = 'new_for_backend'
                await to_backend_queue.enqueue(frontend_msg)

            await asyncio.sleep(0.1)
        except Exception as e:
            logger.error(f"Error in queue forwarding: {e}")
            await asyncio.sleep(1)
