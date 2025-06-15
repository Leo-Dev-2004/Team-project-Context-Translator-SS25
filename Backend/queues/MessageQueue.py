# Backend/queues/MessageQueue.py
import asyncio
import logging
import time
from typing import Dict, Optional, Union, Any, cast, Deque
from collections import deque

# Import the abstract type and the global 'queues' instance
from Backend.queues.queue_types import AbstractMessageQueue # Import the abstract type
from Backend.core.Queues import queues # STILL import the global instance from its correct location

from Backend.models.message_types import QueueMessage, DeadLetterMessage, ForwardingPathEntry

logger = logging.getLogger(__name__)

# Make MessageQueue inherit from AbstractMessageQueue (for type correctness)
class MessageQueue(asyncio.Queue, AbstractMessageQueue): # <-- Inherit from AbstractMessageQueue
    _queue: deque
    """
    A custom message queue inheriting from asyncio.Queue to handle Pydantic message objects.
    It adds a name for logging and ensures type validation for enqueued items.
    """

    def get_items_snapshot(self) -> list[Dict[str, Any]]:
        """ Returns a snapshot (list) of all messages currently in the queue without removing them."""
        # Access the internal deque managed by asyncio.Queue
        return list(self._queue)

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
        
    def peek(self) -> Optional[Union[QueueMessage, DeadLetterMessage]]:
        """
        Peeks at the first item in the queue without removing it.
        Returns the item or None if the queue is empty.
        """
        if self.empty():
            return None
        return self._queue[0] # Correctly accessing the internal deque


async def initialize_and_assert_queues() -> None:
        """
        Initializes all singleton queues and populates the global shared_queues instance.
        This function must be called once at application startup.
        It also asserts that all queues have been successfully initialized.
        """
        # Define the names of the queues we expect to initialize
        expected_queue_names = [
            "to_frontend",
            "from_frontend",
            "to_backend",
            "from_backend",
            "dead_letter",
        ]

        # Only initialize if they haven't been already (e.g., if to_frontend is None)
        if queues.to_frontend is None:
            logger.info(f"Initializing all queues on event loop {id(asyncio.get_running_loop())}...")
            
            # Initialize the queues directly on the shared_queues object
            queues.to_frontend = MessageQueue(maxsize=100, name="to_frontend")
            queues.from_frontend = MessageQueue(maxsize=100, name="from_frontend")
            queues.to_backend = MessageQueue(maxsize=100, name="to_backend")
            queues.from_backend = MessageQueue(maxsize=100, name="from_backend")
            queues.dead_letter = MessageQueue(maxsize=0, name="dead_letter")
            
            initialized_queue_names = [getattr(queues, name).name for name in expected_queue_names]
            logger.info(f"All queues initialized: {initialized_queue_names}")
        else:
            logger.info("Queues already initialized.")

        # --- CLEVER ASSERTION BLOCK ---
        # Iterate through the expected queue names and assert that each one is not None
        for queue_name in expected_queue_names:
            # Use getattr to dynamically get the attribute from shared_queues
            queue_instance = getattr(queues, queue_name)
            assert queue_instance is not None, f"Queue '{queue_name}' was not initialized! It is None."
            # Optional: You can also assert its type if you want stricter checks
            assert isinstance(queue_instance, MessageQueue), \
                f"Queue '{queue_name}' is not a MessageQueue instance!"
        # --- END CLEVER ASSERTION BLOCK ---

        logger.info("Shared queues initialized and asserted as not None.")
