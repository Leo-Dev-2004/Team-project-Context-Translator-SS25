import asyncio
import threading
import uuid
import time
import logging
from typing import Dict
from collections import deque

logger = logging.getLogger(__name__)

class MessageQueue:
    def __init__(self, max_size: int = 100, name: str = "UnnamedQueue"):
        self._queue = deque(maxlen=max_size)
        self._name = name
        self._lock = asyncio.Lock()
        self._not_empty = asyncio.Condition(self._lock)
        self._not_full = asyncio.Condition(self._lock)
        self._max_size = max_size

    async def enqueue(self, message: Dict) -> None:
        async with self._lock:
            while len(self._queue) >= self._max_size:
                logger.debug(f"Queue '{self._name}' full, waiting to enqueue...")
                await self._not_full.wait()

            self._queue.append(message)
            logger.debug(f"Enqueued to '{self._name}', size: {len(self._queue)}")
            self._not_empty.notify()

    async def dequeue(self) -> Dict:
        async with self._lock:
            while not self._queue:
                logger.debug(f"Queue '{self._name}' empty, waiting to dequeue...")
                await self._not_empty.wait()

            item = self._queue.popleft()
            self._not_full.notify()
            return item

    def size(self) -> int:
        return len(self._queue)

    async def clear(self) -> None:
        async with self._lock:
            self._queue.clear()
            self._not_empty.notify_all()
            self._not_full.notify_all()

# Global queue instances - initialized once
to_frontend_queue: MessageQueue = None  
from_frontend_queue: MessageQueue = None
to_backend_queue: MessageQueue = None
from_backend_queue: MessageQueue = None
dead_letter_queue: MessageQueue = None

def init_queues():
    global to_frontend_queue, from_frontend_queue, to_backend_queue, from_backend_queue, dead_letter_queue
    if None in [to_frontend_queue, from_frontend_queue, to_backend_queue, from_backend_queue]:
        to_frontend_queue = MessageQueue(max_size=100, name="to_frontend")
        from_frontend_queue = MessageQueue(max_size=100, name="from_frontend") 
        to_backend_queue = MessageQueue(max_size=100, name="to_backend")
        from_backend_queue = MessageQueue(max_size=100, name="from_backend")
        dead_letter_queue = MessageQueue(max_size=100, name="dead_letter")
        logger.info("All queues initialized")
    else:
        logger.info("Queues already initialized")
