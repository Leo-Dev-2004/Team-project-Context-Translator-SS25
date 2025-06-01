import asyncio
import logging
from typing import Dict, Any, Optional
from collections import deque

logger = logging.getLogger(__name__)

class MessageQueue:
    def __init__(self, name: str, max_size: int = 100):
        self.name = name
        self._queue = deque(maxlen=max_size)
        self._lock = asyncio.Lock()
        self._not_empty = asyncio.Condition(self._lock)
        logger.info(f"Initialized MessageQueue '{name}'")

    async def enqueue(self, message: Dict[str, Any]):
        async with self._lock:
            self._queue.append(message)
            self._not_empty.notify_all()
            logger.debug(f"Enqueued message to '{self.name}': {message.get('type', 'N/A')}")

    async def dequeue(self) -> Optional[Dict[str, Any]]:
        async with self._not_empty:
            while len(self._queue) == 0:
                await self._not_empty.wait()
            return self._queue.popleft()

    def size(self) -> int:
        return len(self._queue)

# Singleton Queue Instances
_queues = {}

def get_queue(queue_name: str) -> MessageQueue:
    if queue_name not in _queues:
        _queues[queue_name] = MessageQueue(queue_name)
    return _queues[queue_name]

def get_from_frontend_queue() -> MessageQueue:
    return get_queue("from_frontend")

def get_to_frontend_queue() -> MessageQueue:
    return get_queue("to_frontend")

def get_dead_letter_queue() -> MessageQueue:
    return get_queue("dead_letter")
