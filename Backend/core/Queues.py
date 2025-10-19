# Backend/core/Queues.py
from ..queues.QueueTypes import AbstractMessageQueue # Korrigierter Importpfad
from ..queues.MessageQueue import MessageQueue # Korrigierter Importpfad
import logging
from typing import Optional # Importieren für Type Hinting

logger = logging.getLogger(__name__)

class Queues:
    """Manages all global message queues for the application."""

    _instance: Optional["Queues"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Queues, cls).__new__(cls)
            cls._instance._initialized = False # Use a flag to ensure single initialization
        return cls._instance

    def __init__(self):
        if not self._initialized:
            logger.info("Initializing global message queues...")
            self.incoming: AbstractMessageQueue = MessageQueue()
            self.outgoing: AbstractMessageQueue = MessageQueue()
            self.websocket_out: AbstractMessageQueue = MessageQueue()
            self._initialized = True
            logger.info("Global message queues initialized.")

    def get_all_queues(self) -> dict[str, AbstractMessageQueue]:
        """Returns a dictionary of all managed queues."""
        return {
            "incoming": self.incoming,
            "outgoing": self.outgoing,
            "websocket_out": self.websocket_out
        }

# Erstelle eine globale Instanz, die von anderen Modulen importiert werden kann
queues = Queues()