import asyncio
import json
import logging
import time
from fastapi import WebSocket
from pydantic import ValidationError
from ..queues.shared_queue import get_to_frontend_queue, get_from_frontend_queue
from ..models.message_types import WebSocketMessage
from ..dependencies import get_simulation_manager

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
            self.connections.add(websocket)

            # Send connection acknowledgment
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
                if not message:
                    continue
                    
                # Validate message format
                if not isinstance(message, dict):
                    logger.error(f"Invalid message format: {type(message)}")
                    continue
                    
                if 'type' not in message:
                    message['type'] = 'unknown'
                    
                if 'data' not in message:
                    message['data'] = {}
                    
                # Create WebSocketMessage
                ws_msg = WebSocketMessage(
                    type=message['type'],
                    data=message.get('data', {}),
                    client_id=message.get('client_id', str(websocket.client)),
                    timestamp=message.get('timestamp', time.time())
                )
                
                await websocket.send_text(ws_msg.json())
                logger.debug(f"Sent WebSocket message: {message['type']}")
                
            except Exception as e:
                logger.error(f"Send error: {e}")
                break

    async def _receiver(self, websocket: WebSocket):
        """Receive messages from client and add to from_frontend_queue"""
        while True:
            try:
                data = await websocket.receive_text()
                logger.debug(f"Received raw WebSocket data: {data}")
                
                try:
                    # Step 1: Basic JSON validation
                    try:
                        message_dict = json.loads(data)
                    except json.JSONDecodeError as e:
                        await self._send_error(websocket, f"Invalid JSON: {str(e)}")
                        continue

                    # Step 2: Required field validation
                    if not isinstance(message_dict, dict):
                        await self._send_error(websocket, "Message must be a JSON object")
                        continue
                        
                    required_fields = ['type', 'data']
                    missing_fields = [field for field in required_fields if field not in message_dict]
                    if missing_fields:
                        await self._send_error(websocket, f"Missing required fields: {', '.join(missing_fields)}")
                        continue

                    # Step 3: Type-specific validation
                    if message_dict['type'] == 'test_message':
                        if not isinstance(message_dict.get('data', {}).get('id'), str):
                            await self._send_error(websocket, "Test messages require string 'id' in data")
                            continue

                    # Step 4: Full Pydantic validation
                    try:
                        message = WebSocketMessage.parse_raw(data)
                    except ValidationError as e:
                        error_details = "; ".join([f"{err['loc'][0]}: {err['msg']}" for err in e.errors()])
                        await self._send_error(websocket, f"Validation failed: {error_details}")
                        continue

                    # Step 5: Enqueue validated message
                    queue_msg = {
                        'type': message.type,
                        'data': message.data,
                        'timestamp': message.timestamp,
                        'client_id': str(websocket.client),
                        'processing_path': message_dict.get('processing_path', []),
                        'forwarding_path': message_dict.get('forwarding_path', [])
                    }
                    
                    logger.info(f"Enqueuing valid message of type '{message.type}'")
                    await get_from_frontend_queue().enqueue(queue_msg)
                except json.JSONDecodeError:
                    await self._send_error(websocket, "Invalid JSON format")
                except ValidationError as e:
                    logger.error(f"Invalid WebSocket message: {e}")
                    await self._send_error(websocket, f"Invalid message: {e.errors()[0]['msg']}")
            except Exception as e:
                logger.error(f"Receive error: {e}")
                break

    async def _send_ack(self, websocket: WebSocket):
        """Send connection acknowledgment"""
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
        
        # Check WebSocket state before attempting to close
        if websocket.client_state != WebSocketState.DISCONNECTED:
            try:
                await websocket.close(code=1000)  # 1000 = normal closure
                logger.info(f"Closed WebSocket connection for {client_info}")
            except RuntimeError as e:
                # Already closing/closed
                logger.debug(f"WebSocket already closing for {client_info}: {e}")
            except Exception as e:
                logger.error(f"Unexpected error closing WebSocket for {client_info}: {e}")
        else:
            logger.debug(f"WebSocket for {client_info} was already disconnected")

        logger.info(f"Connection cleanup completed for {client_info}")

    async def _send_error(self, websocket: WebSocket, error_msg: str):
        """Send error response to client"""
        try:
            error_response = {
                "type": "error",
                "message": error_msg,
                "timestamp": time.time()
            }
            await websocket.send_text(json.dumps(error_response))
        except Exception as e:
            logger.error(f"Failed to send error message: {e}")

    def get_metrics(self):
        """Get WebSocket metrics"""
        return {
            "connections": len(self.connections),
            "acknowledged_connections": len(self.ack_status)
        }

    async def shutdown(self):
        """Clean shutdown of all connections"""
        for websocket in list(self.connections):
            await self._cleanup_connection(websocket, "shutdown")

    async def handle_message(self, websocket: WebSocket, raw_data: str):
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
