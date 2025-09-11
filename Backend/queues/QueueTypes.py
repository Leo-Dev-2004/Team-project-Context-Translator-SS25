# Backend/queues/QueueTypes.py
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Union

# Import the ONE UniversalMessage type
from Backend.models.UniversalMessage import UniversalMessage, ForwardingPathEntry

# defines the abstract interface (protocol/ABC) for any message queue implementation in your system (AbstractMessageQueue). It specifies what methods a queue must have (e.g., enqueue, dequeue, qsize, peek, drain).
class AbstractMessageQueue(ABC):
    """
    Abstract base class defining the interface for message queues in the system.
    All concrete queue implementations must adhere to this interface.
    """
    @property
    @abstractmethod
    def name(self) -> str:
        """The name of the queue for identification and logging."""
        pass

    @abstractmethod
    async def enqueue(self, item: UniversalMessage) -> None:
        """
        Asynchronously adds a UniversalMessage item to the queue.
        Implementations should handle potential QueueFull errors.
        """
        pass

    @abstractmethod
    async def dequeue(self) -> UniversalMessage:
        """
        Asynchronously retrieves and removes a UniversalMessage item from the queue.
        Blocks until an item is available.
        """
        pass

    @abstractmethod
    def qsize(self) -> int:
        """Returns the current number of items in the queue."""
        pass

    @abstractmethod
    def get_items_snapshot(self) -> list[Dict[str, Any]]: # Removed Dict from outer Union as we enforce UniversalMessage
        """
        Returns a snapshot (list of dictionaries) of all messages currently in the queue
        without removing them. Useful for debugging and monitoring.
        """
        pass

    @abstractmethod
    async def drain(self, timeout: Optional[float] = None) -> None:
        """
        Asynchronously removes all currently available items from the queue.
        Can be used during shutdown or for cleanup.
        """
        pass

    @abstractmethod
    def peek(self) -> Optional[UniversalMessage]: # Removed Dict from outer Union
        """
        Peeks at the first item in the queue without removing it.
        Returns the item or None if the queue is empty.
        """
        pass