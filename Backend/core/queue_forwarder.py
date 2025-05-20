import asyncio
import logging
from ..queues.shared_queue import (
    get_from_backend_queue,
    get_to_frontend_queue,
    get_from_frontend_queue,
    get_to_backend_queue
)

logger = logging.getLogger(__name__)

class QueueForwarder:
    def __init__(self):
        self.from_backend_queue = get_from_backend_queue()
        self.to_frontend_queue = get_to_frontend_queue()
        self.from_frontend_queue = get_from_frontend_queue()
        self.to_backend_queue = get_to_backend_queue()

    async def forward(self):
        """Forward messages between queues"""
        logger.info("Starting queue forwarder")
        while True:
            try:
                # Forward from backend to frontend
                msg = await self.from_backend_queue.dequeue()
                if msg is None:
                    continue
                    
                msg.setdefault('forwarding_path', [])
                msg['forwarding_path'].append({
                    'from': 'from_backend_queue',
                    'to': 'to_frontend_queue',
                    'timestamp': time.time()
                })
                
                await self.to_frontend_queue.enqueue(msg)
                logger.debug(f"Forwarded message {msg['data']['id']} to frontend")

                # Forward from frontend to backend
                frontend_msg = await self.from_frontend_queue.dequeue()
                if frontend_msg:
                    frontend_msg['status'] = 'new_for_backend'
                    await self.to_backend_queue.enqueue(frontend_msg)

                await asyncio.sleep(0.1)
            except Exception as e:
                logger.error(f"Error in queue forwarding: {e}")
                await asyncio.sleep(1)
