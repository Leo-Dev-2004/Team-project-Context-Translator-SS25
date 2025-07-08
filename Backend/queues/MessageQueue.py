# Backend/queues/MessageQueue.py

import asyncio
import logging
import time
from typing import Dict, Optional, Any, Deque
from collections import deque

# Import the abstract type
from ..queues.QueueTypes import AbstractMessageQueue

from ..models.UniversalMessage import UniversalMessage, ForwardingPathEntry

logger = logging.getLogger(__name__)

class MessageQueue(asyncio.Queue, AbstractMessageQueue):
    # This type hint for _queue is an implementation detail of asyncio.Queue (private attribute)
    # It's here for clarity but strictly speaking might not be necessary for external use.
    _queue: deque[UniversalMessage]

    """
    A custom message queue inheriting from asyncio.Queue, designed to hold UniversalMessage objects.
    It adds a name for logging, ensures type consistency, and includes path tracking features.
    """

    def __init__(self, maxsize: int = 0, name: str = "default"):
        # Initialize asyncio.Queue with type hint for items
        super().__init__(maxsize=maxsize)
        self._name = name
        logger.debug(f"MessageQueue '{self._name}' initialized with maxsize={maxsize}.")

    @property
    def name(self) -> str:
        return self._name

    def get_items_snapshot(self) -> list[Dict[str, Any]]:
        """
        Returns a snapshot (list of dictionaries) of all messages currently in the queue without removing them.
        Useful for debugging and monitoring.
        """
        # Access the internal deque managed by asyncio.Queue and convert items to dicts
        # Ensure that items are UniversalMessage and thus have .model_dump()
        return [item.model_dump() for item in self._queue]

    async def enqueue(self, item: UniversalMessage):
        """
        Enqueues a UniversalMessage object into the queue.
        Performs type validation and updates the message's forwarding path.
        """
        # Strict type validation: ensuring only UniversalMessage instances are accepted
        # This check is good practice, though with strict type hints it's caught by static analysis.
        if not isinstance(item, UniversalMessage):
            logger.error(
                f"Invalid item type for queue '{self.name}'. "
                f"Expected UniversalMessage, got {type(item).__name__}: {item}"
            )
            raise ValueError(
                f"Invalid message format for queue '{self.name}'. "
                f"Expected UniversalMessage instance."
            )

        try:
            # Add to forwarding path
            item.forwarding_path.append(ForwardingPathEntry(
                router="MessageQueue_enqueue",  # Router/component doing the enqueuing
                timestamp=time.time(),
                to_queue=self.name,
                from_queue=None,
                details={"info": "enqueued"}
            ))

            if (item.type != 'system.queue_status_update'):
                logger.debug(
                    f"Putting item (ID: {item.id}, type: {item.type}, dest: {item.destination}) "
                    f"into '{self.name}' queue. Current size before put: {self.qsize()}"
                )
            await self.put(item)  # Use asyncio.Queue's put method

            
        except asyncio.QueueFull:
            logger.warning(
                f"Queue '{self.name}' is full. Message (ID: {item.id}) "
                f"dropped or will block if maxsize is set and put is awaited."
            )
            raise # Re-raise if you want blocking behavior to propagate
        except Exception as e:
            logger.error(
                f"Error putting item (ID: {item.id}) into '{self.name}' queue: {e}",
                exc_info=True
            )
            raise # Re-raise to propagate the error

    async def dequeue(self) -> UniversalMessage:
        """
        Retrieves a UniversalMessage object from the queue.
        Blocks until an item is available. Updates the message's forwarding path.
        """
        # logger.debug(f"Queue '{self.name}' empty, waiting to dequeue..." if self.empty() else f"Dequeuing from '{self.name}', size: {self.qsize()}")

        item: UniversalMessage = await self.get()
        
        # --- ADD THE DELAY HERE! ---
        # This simulates the time it takes to process the message *after* it has been
        # taken from the queue but *before* the dequeue operation is fully complete
        # or before the caller gets control back and potentially calls task_done().
        # IMPORTANT: The qsize will show -1 immediately after self.get().
        # To actually see a backlog, messages must be *added* faster than they are removed.
        # However, this delay will make the *entire system* slow down when consuming messages.
        # The effect on *queue size* visibility is indirect, but it makes the processing
        # visually slower.
        # await asyncio.sleep(2) # Adjust delay as needed (e.g., 0.5 to 2.0 seconds)

        
        self.task_done() # Signal that a task processing this item is complete

        # Add to forwarding path
        item.forwarding_path.append(ForwardingPathEntry(
            router="MessageQueue_dequeue", # Router/component doing the dequeuing
            timestamp=time.time(),
            to_queue=None,
            from_queue=self.name,
            details={"status": "dequeued"}
        ))

        #logger.debug(
        #    f"Dequeued item (ID: {item.id}, type: {item.type}, dest: {item.destination}) "
        #    f"from '{self.name}' queue. Current size: {self.qsize()}"
        #)
        return item

    async def drain(self, timeout: Optional[float] = None) -> None:
        """
        Drains the queue by getting all currently available items.
        Can be used during shutdown to ensure all messages are processed or cleared.
        """
        logger.info(f"Draining queue '{self.name}' (current size: {self.qsize()})...")
        while not self.empty():
            try:
                await asyncio.wait_for(self.get(), timeout=timeout if timeout else 0.1)
                self.task_done()
            except asyncio.TimeoutError:
                break
            except Exception as e:
                logger.error(f"Error during draining queue '{self.name}': {e}", exc_info=True)
        logger.info(f"Queue '{self.name}' drained. Final size: {self.qsize()}.")

    def peek(self) -> Optional[UniversalMessage]:
        """
        Peeks at the first item in the queue without removing it.
        Returns the item or None if the queue is empty.
        Note: This is an internal detail of asyncio.Queue's `_queue` attribute (a deque).
        """
        if self.empty():
            return None
        # Access the underlying deque for peeking
        return self._queue[0]