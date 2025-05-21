import asyncio
import json
import logging
import time
from fastapi import WebSocket
from ..queues.shared_queue import get_to_frontend_queue, get_from_frontend_queue
from ..models.message_types import WebSocketMessage

logger = logging.getLogger(__name__)

class WebSocketManager:
    def __init__(self):
        self.connections = set()
        self.ack_status = {}

    async def handle_connection(self, websocket: WebSocket):
        """Handle new WebSocket connection"""
        client = websocket.client
        client_info = f"{client.host}:{client.port}" if client else "unknown"
        
        try:
            await websocket.accept()
            self.connections.add(websocket)
            
            # Send connection ack
            await self._send_ack(websocket)
            
            # Start sender/receiver tasks
            sender = asyncio.create_task(self._sender(websocket))
            receiver = asyncio.create_task(self._receiver(websocket))
            
            await asyncio.wait(
                [sender, receiver],
                return_when=asyncio.FIRST_COMPLETED
            )
            
        except Exception as e:
            logger.error(f"Connection error for {client_info}: {e}")
        finally:
            await self._cleanup_connection(websocket, client_info)

    async def _sender(self, websocket: WebSocket):
        """Send messages from to_frontend_queue to client"""
        while True:
            try:
                message = await get_to_frontend_queue().dequeue()
                await websocket.send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Send error: {e}")
                break

    async def _receiver(self, websocket: WebSocket):
        """Receive messages from client and add to from_frontend_queue"""
        while True:
            try:
                data = await websocket.receive_text()
                message = WebSocketMessage(**json.loads(data))
                await get_from_frontend_queue().enqueue(message.dict())
            except Exception as e:
                logger.error(f"Receive error: {e}")
                break

    async def _send_ack(self, websocket: WebSocket):
        """Send connection acknowledgement"""
        ack = {
            "type": "connection_ack",
            "status": "connected",
            "timestamp": time.time()
        }
        await websocket.send_text(json.dumps(ack))
        self.ack_status[websocket] = True

    async def _cleanup_connection(self, websocket: WebSocket, client_info: str):
        """Clean up connection resources"""
        self.connections.discard(websocket)
        self.ack_status.pop(websocket, None)
        try:
            await websocket.close()
        except:
            pass
        logger.info(f"Connection closed for {client_info}")

    def get_metrics(self):
        """Get WebSocket metrics"""
        return {
            "connections": len(self.connections),
            "ack_status": len(self.ack_status)
        }

    async def shutdown(self):
        """Clean shutdown of all connections"""
        for websocket in list(self.connections):
            await self._cleanup_connection(websocket, "shutdown")    async def handle_message(self, websocket: WebSocket, raw_data: str):
        """Handle incoming WebSocket message"""
        try:
            # Validate message structure
            try:
                msg = WebSocketMessage.parse_raw(raw_data)
                msg.client_id = msg.client_id or str(websocket.client)
            except ValidationError as e:
                logger.error(f"Invalid WS message: {e}")
                await self._send_error(websocket, "Invalid message format")
                return

            # Process based on message type
            if msg.type == 'command':
                await self._handle_command(msg)
            elif msg.type == 'data':
                await self._handle_data(msg)
            else:
                await self._send_error(websocket, f"Unknown message type: {msg.type}")

        except Exception as e:
            logger.error(f"Message handling error: {e}")
            await self._send_error(websocket, "Processing error")

    async def _handle_command(self, msg: WebSocketMessage):
        """Handle command messages"""
        command = msg.data.get('command')
        if command == 'start_simulation':
            await get_simulation_manager().start()
        elif command == 'stop_simulation':
            await get_simulation_manager().stop()
        # ... other commands ...

    async def _handle_data(self, msg: WebSocketMessage):
        """Handle data messages"""
        await get_from_frontend_queue().enqueue({
            'type': msg.type,
            'data': msg.data,
            'timestamp': msg.timestamp,
            'client_id': msg.client_id
        })
