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
                msg = await self._from_backend_queue.dequeue()
                if msg is None:
                    continue
                    
                msg.setdefault('forwarding_path', [])
                msg['forwarding_path'].append({
                    'from': 'from_backend_queue',
                    'to': 'to_frontend_queue',
                    'timestamp': time.time()
                })
                
                await self._to_frontend_queue.enqueue(msg)
                logger.debug(f"Forwarded message {msg['data']['id']} to frontend")

                # Forward from frontend to backend
                frontend_msg = await self._from_frontend_queue.dequeue()
                if frontend_msg:
                    frontend_msg['status'] = 'new_for_backend'
                    await self._to_backend_queue.enqueue(frontend_msg)

                await asyncio.sleep(0.1)
            except Exception as e:
                logger.error(f"Error in queue forwarding: {e}")
                await asyncio.sleep(1)
