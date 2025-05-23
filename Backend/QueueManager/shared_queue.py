import threading
import uuid # Recommended for unique IDs
import time
from typing import Dict


queue_lock = threading.Lock()
detection_queue = [] # Consider using collections.deque for efficiency with pop/append

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

def update_entry(entry_id: str, explanation: str = None, status: str = None):
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

def get_entry_history(status_filter: list[str] = None, term_filter: str = None) -> list[dict]:
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


def cleanup_queue(limited: int | str = None) -> None:
    """
    Function to remove old or irrelevant entries. 
    """
    if limited is None:
        return
    now = time.time()
    with queue_lock:
        # check if the entry is out of date
        if isinstance(limited, int):
            detection_queue[:] = [e for e in detection_queue if (now - e.get("timestamp")) < limited]
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
