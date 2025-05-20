import asyncio
import threading
import uuid
import time
import logging
from typing import Dict, List, Optional
from collections import deque

logger = logging.getLogger(__name__)

class MessageQueue:
    def __init__(self, max_size: int = 100, name: str = "UnnamedQueue"):
        self._queue = deque(maxlen=max_size)
        self._name = name
        self._not_empty = asyncio.Condition()
        self._not_full = asyncio.Condition()
        self._max_size = max_size

    async def enqueue(self, message: Dict) -> None:
        """Add message to queue and notify waiting coroutines"""
        async with self._not_full:
            while len(self._queue) >= self._max_size:
                logger.debug(f"Queue '{self._name}' full, waiting to enqueue...")
                await self._not_full.wait()

            self._queue.append(message)
            logger.debug(f"Enqueued to '{self._name}', size: {len(self._queue)}")
            self._not_empty.notify()

    async def dequeue(self) -> Dict:
        """Remove and return message from queue (blocks until available)"""
        async with self._not_empty:
            while not self._queue:
                logger.debug(f"Queue '{self._name}' empty, waiting to dequeue...")
                await self._not_empty.wait()

            item = self._queue.popleft()
            self._not_full.notify()
            return item

    def size(self) -> int:
        """Get current queue size"""
        return len(self._queue)

    def clear(self) -> None:
        """Clear all items from queue"""
        self._queue.clear()
        # Notify all waiting tasks to prevent deadlocks
        async def _notify_all():
            async with self._not_empty:
                self._not_empty.notify_all()
            async with self._not_full:
                self._not_full.notify_all()
        asyncio.create_task(_notify_all())

# Initialize all queues with descriptive names and size limits
to_frontend_queue = MessageQueue(max_size=100, name="to_frontend")
from_frontend_queue = MessageQueue(max_size=100, name="from_frontend")
to_backend_queue = MessageQueue(max_size=100, name="to_backend")
from_backend_queue = MessageQueue(max_size=100, name="from_backend")
dead_letter_queue = MessageQueue(max_size=100, name="dead_letter")

# Legacy queue and lock for backward compatibility
queue_lock = threading.Lock()
detection_queue = deque()

def add_entry(entry: dict):
    """Adds a new detection object to the central Queue."""
    with queue_lock:
        # Add unique ID and set initial status if not already present
        if 'id' not in entry:
            entry['id'] = str(uuid.uuid4())
        if 'status' not in entry: 
             entry['status'] = 'pending'
        if 'explanation' not in entry:
            entry['explanation'] = None 
        if 'timestamp' not in entry:
            entry['timestamp'] = time.time()
        detection_queue.append(entry)
        # Optional: Log the addition

def get_pending_entries() -> list[dict]:
    """Retrieves all entries with status 'pending'. Returns a copy to avoid external modification issues."""
    with queue_lock:
        # Filter and return a copy of the relevant entries
        pending = [e.copy() for e in detection_queue if e.get('status') == 'pending']
        # Consider sorting by timestamp if processing order matters

        return list(pending) # Return a copy

def update_entry(entry_id: str, explanation: Optional[str] = None, status: Optional[str] = None):
    """Updates the status and explanation for a specific entry by ID."""
    with queue_lock:
        found = False
        for entry in detection_queue:
            if entry.get('id') == entry_id:
                if status is not None:
                    entry['status'] = status

                if explanation is not None:
                    entry['explanation'] = explanation

                entry['timestamp'] = time.time()
                found = True
                # Optional: Log the update
                break
        if not found:
            # Optional: Log a warning if entry_id not found
            pass

def get_entry_history(status_filter: Optional[list[str]] = None, term_filter: Optional[str] = None) -> list[dict]:
    """
    Retrieve historical entries from the queue, potentially filtered by status or term,
    for use in Main Model prompt building or UI display.
    """
    with queue_lock:
        history = detection_queue.copy()

        # get the entries by filter
        if status_filter:
            history = [e for e in history if e.get('status') in status_filter]

        if term_filter:
            history = [e for e in history if e.get('term') == term_filter]

        return [e.copy() for e in history]


from typing import Optional

def cleanup_queue(limited: Optional[int | str] = None) -> None:
    if detection_queue:
        """
        Function to remove old or irrelevant entries. 
        """
        if limited is None:
            return
        now = time.time()
        with queue_lock:
            # check if the entry is out of date
            if isinstance(limited, int):
                filtered_entries = [e for e in detection_queue if (now - e.get("timestamp")) < limited]
                detection_queue.clear()
                detection_queue.extend(filtered_entries)
            # to be implemented: irrelevant

def get_status_summary() -> Dict[str, int]:
    """
    Return counts of entries per status for monitoring.
    """
    summary: Dict[str, int] = {} # initial the summary
    with queue_lock:
        for entry in detection_queue:
            status = entry.get("status") 
            summary[status] = summary.get(status, 0) + 1 # add 1 to the correspond status
    return summary
