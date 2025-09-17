import logging
from typing import Dict
from fastapi import WebSocket

logger = logging.getLogger(__name__)

class ConnectionManager:
    """Manages active WebSocket connections, mapping client_id to WebSocket objects."""
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, client_id: str):
        """Accepts a new WebSocket connection and maps it to a client ID."""
        await websocket.accept()
        self.active_connections[client_id] = websocket
        logger.info(f"Client connected: {client_id}")

    def disconnect(self, client_id: str):
        """Removes a client's WebSocket connection."""
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            logger.info(f"Client disconnected: {client_id}")

    async def send_to_client(self, client_id: str, message: str):
        """Sends a JSON string message to a specific client."""
        if client_id in self.active_connections:
            websocket = self.active_connections[client_id]
            try:
                await websocket.send_text(message)
                logger.info(f"Sent message to {client_id}")
            except Exception as e:
                logger.error(f"Failed to send message to {client_id}: {e}")
                # The connection might be closed, so we clean it up.
                self.disconnect(client_id)
        else:
            logger.warning(f"Attempted to send message to disconnected or unknown client: {client_id}")