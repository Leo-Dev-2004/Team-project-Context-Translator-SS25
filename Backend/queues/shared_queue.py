import asyncio
import logging
from typing import Dict, Optional
from collections import deque

logger = logging.getLogger(__name__)

class MessageQueue:
    def __init__(self, max_size: int = 100, name: str = "UnnamedQueue"):
        self._queue = deque(maxlen=max_size)
        self._name = name
        self._max_size = max_size
        self._lock = None
        self._not_empty = None
        self._not_full = None
        self._initialized = False

    async def initialize(self):
        """Initialize async primitives in the current event loop"""
        if not self._initialized:
            self._lock = asyncio.Lock()
            self._not_empty = asyncio.Condition(self._lock)
            self._not_full = asyncio.Condition(self._lock)
            self._initialized = True
            logger.debug(f"Initialized queue '{self._name}' on loop {id(asyncio.get_running_loop())}")

    async def enqueue(self, message: Dict) -> None:
        if not self._initialized:
            await self.initialize()
            
        async with self._lock:
            while len(self._queue) >= self._max_size:
                logger.debug(f"Queue '{self._name}' full, waiting to enqueue...")
                await self._not_full.wait()

            self._queue.append(message)
            logger.debug(f"Enqueued to '{self._name}', size: {len(self._queue)}")
            self._not_empty.notify()

    async def dequeue(self) -> Dict:
        if not self._initialized:
            await self.initialize()
            
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
        if not self._initialized:
            await self.initialize()
            
        async with self._lock:
            self._queue.clear()
            self._not_empty.notify_all()
            self._not_full.notify_all()

# Global dictionary to hold initialized queues
_initialized_queues: Dict[str, MessageQueue] = {}

async def get_initialized_queues() -> Dict[str, MessageQueue]:
    """Initialize and return all queues in current event loop"""
    global _initialized_queues
    
    if not _initialized_queues:
        logger.info("Initializing all queues...")
        _initialized_queues["to_frontend"] = MessageQueue(max_size=100, name="to_frontend")
        _initialized_queues["from_frontend"] = MessageQueue(max_size=100, name="from_frontend")
        _initialized_queues["to_backend"] = MessageQueue(max_size=100, name="to_backend")
        _initialized_queues["from_backend"] = MessageQueue(max_size=100, name="from_backend")
        _initialized_queues["dead_letter"] = MessageQueue(max_size=100, name="dead_letter")

        # Initialize async primitives
        for queue in _initialized_queues.values():
            await queue.initialize()
        
        logger.info(f"All queues initialized on loop {id(asyncio.get_running_loop())}")
    
    return _initialized_queues

def get_queue(queue_name: str) -> MessageQueue:
    """Get specific queue by name"""
    if queue_name not in _initialized_queues:
        raise RuntimeError(f"{queue_name} not initialized. Call get_initialized_queues() first")
    return _initialized_queues[queue_name]

def get_to_frontend_queue() -> MessageQueue:
    return get_queue("to_frontend")

def get_from_frontend_queue() -> MessageQueue:
    return get_queue("from_frontend")

def get_to_backend_queue() -> MessageQueue:
    return get_queue("to_backend")

def get_from_backend_queue() -> MessageQueue:
    return get_queue("from_backend")

def get_dead_letter_queue() -> MessageQueue:
    return get_queue("dead_letter")
