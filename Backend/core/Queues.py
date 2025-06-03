# Backend/core/Queues.py
# Purpose: This file acts as the central registry or singleton container for all the named message queues used throughout your backend application. It's where you define the queues object (e.g., queues.incoming, queues.outgoing). It provides a single point of access for any part of your application that needs to interact with these global queues.

from typing import Optional, TYPE_CHECKING
# Import the concrete MessageQueue implementation
# Make sure Backend.queues.MessageQueue exists and defines MessageQueue
from Backend.queues.MessageQueue import MessageQueue
# Import the abstract type for type hinting consistency
from Backend.queues.queue_types import AbstractMessageQueue

class Queues:
    """
    A singleton container for all global message queues used throughout the backend.
    These queues are initialized directly upon instantiation of the Queues object,
    ensuring they are always available and not None.
    """
    def __init__(self):
        # Queues are now directly initialized with MessageQueue instances.
        # This makes them non-Optional after the Queues object is created.
        self.incoming: AbstractMessageQueue = MessageQueue(maxsize=100, name="incoming") # For all messages entering the backend
        self.outgoing: AbstractMessageQueue = MessageQueue(maxsize=100, name="outgoing") # For all messages leaving a processing step, or meant for frontend
        self.websocket_out: AbstractMessageQueue = MessageQueue(maxsize=100, name="websocket_out") # For messages specifically for WebSocket clients
        self.dead_letter: AbstractMessageQueue = MessageQueue(maxsize=100, name="dead_letter") # For unprocessable messages

# Create a global instance of Queues
# This single instance will be imported by other modules (e.g., simulator, router)
# and will contain fully initialized MessageQueue objects.
queues = Queues()

# Optional: Add a simple assertion block to confirm initialization at startup.
# This isn't strictly for runtime safety (as they are directly initialized),
# but good for confirming expected setup during application load.
import logging
logger = logging.getLogger(__name__)
try:
    # Check that all attributes are indeed instances of MessageQueue and not None
    assert isinstance(queues.incoming, MessageQueue), "Incoming queue not initialized as MessageQueue."
    assert isinstance(queues.outgoing, MessageQueue), "Outgoing queue not initialized as MessageQueue."
    assert isinstance(queues.websocket_out, MessageQueue), "WebSocket Out queue not initialized as MessageQueue."
    assert isinstance(queues.dead_letter, MessageQueue), "Dead Letter queue not initialized as MessageQueue."
    logger.info("Global queues successfully initialized and asserted as MessageQueue instances.")
except AssertionError as e:
    logger.critical(f"FATAL ERROR: Global queues failed to initialize as expected. {e}")
    raise # Re-raise to crash early if a critical setup issue exists.