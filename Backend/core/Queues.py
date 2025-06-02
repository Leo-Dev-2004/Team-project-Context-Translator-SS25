# Backend/core/Queues.py
from typing import Optional, TYPE_CHECKING # Import TYPE_CHECKING to avoid circular imports

# Import the abstract type, not the concrete MessageQueue class
from Backend.queues.queue_types import AbstractMessageQueue

class Queues:
    def __init__(self):
        self.to_frontend: Optional[AbstractMessageQueue] = None
        self.from_frontend: Optional[AbstractMessageQueue] = None
        self.to_backend: Optional[AbstractMessageQueue] = None
        self.from_backend: Optional[AbstractMessageQueue] = None
        self.dead_letter: Optional[AbstractMessageQueue] = None

# Create a global instance of SharedQueues
# This single instance will be imported and populated at startup
queues = Queues() # Use queues as the global instance