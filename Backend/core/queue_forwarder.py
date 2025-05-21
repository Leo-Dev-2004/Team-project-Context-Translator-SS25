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
