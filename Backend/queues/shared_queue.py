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

# Global queue instances - will be initialized when first used
to_frontend_queue: Optional[MessageQueue] = None
from_frontend_queue: Optional[MessageQueue] = None 
to_backend_queue: Optional[MessageQueue] = None
from_backend_queue: Optional[MessageQueue] = None
dead_letter_queue: Optional[MessageQueue] = None

async def initialize_queues():
    """Initialize all queues in the current event loop"""
    global to_frontend_queue, from_frontend_queue, to_backend_queue, from_backend_queue, dead_letter_queue
    
    if to_frontend_queue is None:
        logger.info("Initializing all queues...")
        to_frontend_queue = MessageQueue(max_size=100, name="to_frontend")
        from_frontend_queue = MessageQueue(max_size=100, name="from_frontend")
        to_backend_queue = MessageQueue(max_size=100, name="to_backend")
        from_backend_queue = MessageQueue(max_size=100, name="from_backend")
        dead_letter_queue = MessageQueue(max_size=100, name="dead_letter")
        
        # Initialize async primitives
        await to_frontend_queue.initialize()
        await from_frontend_queue.initialize()
        await to_backend_queue.initialize()
        await from_backend_queue.initialize()
        await dead_letter_queue.initialize()
        
        logger.info(f"All queues initialized on loop {id(asyncio.get_running_loop())}")
