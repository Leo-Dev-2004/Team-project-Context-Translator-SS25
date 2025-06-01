import asyncio
import logging
import time
from typing import Any, Dict, Optional, Union # Removed TypeVar, as it's not needed here
from typing import cast # Import cast for explicit type hinting if needed

# Assuming Backend/models/message.py contains these Pydantic models
from Backend.models.message_types import QueueMessage, DeadLetterMessage, ForwardingPathEntry

logger = logging.getLogger(__name__)

# Removed: T = TypeVar('T', bound=Union[QueueMessage, DeadLetterMessage])
# Pylance prefers direct Union if TypeVar is only used once in a signature.

class MessageQueue(asyncio.Queue):
    """
    A custom message queue inheriting from asyncio.Queue to handle Pydantic message objects.
    It adds a name for logging and ensures type validation for enqueued items.
    """
    def __init__(self, maxsize: int = 0, name: str = "default"):
        super().__init__(maxsize=maxsize)
        self._name = name

        logger.debug(f"MessageQueue '{self._name}' initialized with maxsize={maxsize}.")

    @property
    def name(self) -> str:
        return self._name

    async def enqueue(self, item: Union[QueueMessage, DeadLetterMessage]): # Changed 'item: T' to 'item: Union[...]'
        """
        Enqueues a Pydantic message object into the queue.
        Performs strict type validation to ensure only QueueMessage or DeadLetterMessage instances are accepted.
        """
        # Strict type validation: crucial for preventing "Invalid message format" errors
        if not isinstance(item, (QueueMessage, DeadLetterMessage)):
            logger.error(
                f"Invalid item type for queue '{self.name}'. "
                f"Expected QueueMessage or DeadLetterMessage, got {type(item).__name__}: {item}"
            )
            raise ValueError(
                f"Invalid message format for queue '{self.name}'. "
                f"Expected QueueMessage or DeadLetterMessage instance."
            )

        try:
            # Add to forwarding path if it's a QueueMessage (DeadLetterMessage inherits this)
            if isinstance(item, QueueMessage):
                item.forwarding_path.append(ForwardingPathEntry(
                    processor="MessageQueue_enqueue",
                    timestamp=time.time(),
                    status="enqueued",
                    to_queue=self.name
                ))

            logger.debug(
                f"Putting item (ID: {getattr(item, 'id', 'N/A')}, "
                f"type: {getattr(item, 'type', 'N/A_type')}) "
                f"into '{self.name}' queue. Current size before put: {self.qsize()}"
            )
            await self.put(item)  # Use asyncio.Queue's put method
            logger.debug(
                f"Item put into '{self.name}' queue. "
                f"Current size after put: {self.qsize()}"
            )
        except asyncio.QueueFull:
            logger.warning(
                f"Queue '{self.name}' is full. Message (ID: {getattr(item, 'id', 'N/A')}) "
                f"dropped or will block if maxsize is set and put is awaited."
            )
            raise # Re-raise if you want blocking behavior to propagate
        except Exception as e:
            logger.error(
                f"Error putting item (ID: {getattr(item, 'id', 'N/A')}) into '{self.name}' queue: {e}",
                exc_info=True
            )
            raise # Re-raise to propagate the error

    async def dequeue(self) -> Union[QueueMessage, DeadLetterMessage]: # Changed '-> T' to '-> Union[...]'
        """
        Retrieves a Pydantic message object from the queue.
        Blocks until an item is available.
        """
        logger.debug(f"Queue '{self.name}' empty, waiting to dequeue..." if self.empty() else f"Dequeuing from '{self.name}', size: {self.qsize()}")
        
        # Explicitly cast the result from self.get() to the expected Union type
        item: Union[QueueMessage, DeadLetterMessage] = await self.get() 
        
        self.task_done() # Signal that a task processing this item is complete

        # Add to forwarding path
        if isinstance(item, QueueMessage): # This check is still valid as DeadLetterMessage inherits from QueueMessage
            item.forwarding_path.append(ForwardingPathEntry(
                processor="MessageQueue_dequeue",
                timestamp=time.time(),
                status="dequeued",
                from_queue=self.name
            ))

        logger.debug(
            f"Dequeued item (ID: {getattr(item, 'id', 'N/A')}, "
            f"type: {getattr(item, 'type', 'N/A_type')}) "
            f"from '{self.name}' queue. Current size: {self.qsize()}"
        )
        return item

    async def clear(self) -> None:
        """Clear all items from the queue"""
        while not self.empty():
            try:
                self.get_nowait()
                self.task_done()
            except asyncio.QueueEmpty:
                break

    async def drain(self, timeout: Optional[float] = None) -> None:
        """
        Drains the queue by getting all currently available items.
        Can be used during shutdown to ensure all messages are processed or cleared.
        """
        logger.info(f"Draining queue '{self.name}' (current size: {self.qsize()})...")
        while not self.empty():
            try:
                # Use a small timeout to not block indefinitely if new items keep arriving
                await asyncio.wait_for(self.get(), timeout=timeout if timeout else 0.1)
                self.task_done()
            except asyncio.TimeoutError:
                # If nothing more comes in the timeout, assume drained
                break
            except Exception as e:
                logger.error(f"Error during draining queue '{self.name}': {e}", exc_info=True)
        logger.info(f"Queue '{self.name}' drained. Final size: {self.qsize()}.")

        def get_items_snapshot(self) -> list[Dict[str, Any]]:
            """ Returns a snapshot (list) of all messages currently in the queue without removing them."""
            # Access the internal deque managed by asyncio.Queue
            return list(self._queue)

# Global dictionary to hold initialized queues
_initialized_queues: Dict[str, MessageQueue] = {}


async def get_initialized_queues() -> Dict[str, MessageQueue]:
    """
    Initialize and return all singleton queues within the current event loop.
    This function should be called once at application startup.
    """
    global _initialized_queues
    
    if not _initialized_queues:
        logger.info(f"Initializing all queues on event loop {id(asyncio.get_running_loop())}...")
        _initialized_queues["to_frontend"] = MessageQueue(maxsize=100, name="to_frontend")
        _initialized_queues["from_frontend"] = MessageQueue(maxsize=100, name="from_frontend") # For messages from client to backend
        _initialized_queues["to_backend"] = MessageQueue(maxsize=100, name="to_backend") # For messages from frontend processor to backend logic
        _initialized_queues["from_backend"] = MessageQueue(maxsize=100, name="from_backend") # For messages from backend logic to frontend processor
        _initialized_queues["dead_letter"] = MessageQueue(maxsize=0, name="dead_letter") # No maxsize for DLQ
        
        logger.info(f"All queues initialized: {list(_initialized_queues.keys())}")
    
    return _initialized_queues

def get_queue(queue_name: str) -> MessageQueue:
    """Get a specific queue by name. Assumes queues have been initialized."""
    if queue_name not in _initialized_queues:
        raise RuntimeError(f"Queue '{queue_name}' not initialized. Call get_initialized_queues() first.")
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
