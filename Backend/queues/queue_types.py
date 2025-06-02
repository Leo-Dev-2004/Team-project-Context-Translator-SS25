# Backend/queues/queue_types.py
from abc import ABC, abstractmethod
from typing import Any, Union, Dict, Optional

# Assuming these are external and don't cause circular imports
from Backend.models.message_types import QueueMessage, DeadLetterMessage, ForwardingPathEntry

# Define a minimal interface for MessageQueue that Queues.py can depend on
class AbstractMessageQueue(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    async def enqueue(self, item: Union[QueueMessage, DeadLetterMessage]) -> None:
        pass

    @abstractmethod
    async def dequeue(self) -> Union[QueueMessage, DeadLetterMessage]:
        pass

    @abstractmethod
    def qsize(self) -> int:
        pass

    # Add other methods from MessageQueue that Queues.py might need to type hint
    @abstractmethod
    def get_items_snapshot(self) -> list[Dict[str, Any]]:
        pass
    
    @abstractmethod
    async def drain(self, timeout: Optional[float] = None) -> None:
        """
        Abstract method for draining the queue.
        Concrete implementations must provide this.
        """
        pass

    @abstractmethod
    def peek(self) -> Optional[Union[QueueMessage, DeadLetterMessage]]:
        """
        Abstract method to peek at the next item in the queue without removing it.
        Concrete implementations must provide this.
        """
        pass