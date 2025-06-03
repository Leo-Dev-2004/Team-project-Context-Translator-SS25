# Backend/core/Queues.py
from typing import Optional, TYPE_CHECKING
from Backend.queues.queue_types import AbstractMessageQueue

class Queues:
    def __init__(self):
        self.incoming: Optional[AbstractMessageQueue] = None # For all messages entering the backend
        self.outgoing: Optional[AbstractMessageQueue] = None # For all messages leaving a processing step, or meant for frontend
        self.websocket_out: Optional[AbstractMessageQueue] = None # For messages specifically for WebSocket clients
        self.dead_letter: Optional[AbstractMessageQueue] = None # For unprocessable messages

# Create a global instance of Queues
# This single instance will be imported and populated at startup
queues = Queues()