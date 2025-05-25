# Backend/services/websocket_manager.py

import asyncio
import json
import logging
import time
from typing import Dict, Set, Tuple, Optional
from fastapi import WebSocket
from fastapi.websockets import WebSocketState
from pydantic import ValidationError
from ..queues.shared_queue import get_to_frontend_queue, get_from_frontend_queue
from ..models.message_types import WebSocketMessage
from ..dependencies import get_simulation_manager

logger = logging.getLogger(__name__)

class WebSocketManager:
    def __init__(self) -> None:
        """Initialize WebSocketManager with empty connection sets and task tracking."""
        self.connections: Set[WebSocket] = set()
        self.ack_status: Dict[WebSocket, bool] = {}
        # Maps websocket_id to (sender_task, receiver_task)
        self.active_tasks: Dict[int, Tuple[asyncio.Task, asyncio.Task]] = {}
        """Initialize WebSocketManager with empty connection sets and task tracking."""
        self.connections = set()
        self.ack_status = {}
        # Maps websocket_id to (sender_task, receiver_task)
        self.active_tasks = {}  

    async def handle_connection(self, websocket: WebSocket):
        """Handle new WebSocket connection and manage its lifecycle."""
        client = websocket.client
        client_info = (f"{client.host}:{client.port}" 
                      if client else "unknown")
        websocket_id = id(websocket)

        try:
            await websocket.accept()
            self.connections.add(websocket)
            logger.info(f"New connection: {client_info}. Total connections: {len(self.connections)}")

            # Send connection acknowledgment
            await self._send_ack(websocket)

            # Create tasks with proper error handling
            sender_task = asyncio.create_task(
                self._sender(websocket),
                name=f"sender-{websocket_id}"
            )
            receiver_task = asyncio.create_task(
                self._receiver(websocket),
                name=f"receiver-{websocket_id}"
            )
            self.active_tasks[websocket_id] = (sender_task, receiver_task)

            # Use wait instead of gather for better error handling
            done, pending = await asyncio.wait(
                {sender_task, receiver_task},
                return_when=asyncio.FIRST_COMPLETED
            )

            # Cancel remaining tasks
            for task in pending:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        except Exception as e:
            logger.error(f"Connection lifetime error for {client_info}: {e}", exc_info=True) # Add exc_info for full traceback
        finally:
            logger.info(f"Initiating cleanup for connection: {client_info}")
            # Ensure tasks are cancelled if handle_connection exits for any reason
            # before gather returns
            if websocket_id in self.active_tasks:
                for task in self.active_tasks[websocket_id]:
                    if not task.done(): 
                        task.cancel()
                        try:
                            await task # Await cancellation
                        except asyncio.CancelledError:
                            pass
                del self.active_tasks[websocket_id]
            
            await self._cleanup_connection(websocket, client_info)
            logger.info(f"Cleanup finished for connection: {client_info}. Total connections: {len(self.connections)}")

    async def _sender(self, websocket: WebSocket) -> None:
        """Send messages from to_frontend_queue to client.
        
        Args:
            websocket: The WebSocket connection to send messages through.
        """
        client_info = f"{websocket.client.host}:{websocket.client.port}" if websocket.client else "unknown"
        logger.info(f"Starting sender for {client_info}")

        try:
            while websocket.client_state == WebSocketState.CONNECTED:
                try:
                    message = await get_to_frontend_queue().dequeue()
                    if not message:
                        await asyncio.sleep(0.1)  # Small delay if queue is empty
                        continue

                    if not isinstance(message, dict):
                        logger.error(f"Invalid message format from queue: {type(message)}")
                        continue
                    
                    if 'type' not in message:
                        message['type'] = 'unknown_backend_message' # Assign a default type if missing
                    
                    if 'data' not in message:
                        message['data'] = {}
                    
                    # Ensure WebSocketMessage can parse this structure
                    try:
                        # If message is already a dict that matches WebSocketMessage structure,
                        # you can pass it directly to the constructor or use parse_obj
                        ws_msg = WebSocketMessage(
                            type=message['type'],
                            data=message.get('data', {}),
                            client_id=message.get('client_id', str(websocket.client)),
                            timestamp=message.get('timestamp', time.time())
                        )
                except ValidationError as e:
                    logger.error(
                        "Validation error creating WebSocketMessage in sender: %s",
                        e.errors()
                    )
                    continue  # Skip sending invalid message

                # Wrap send operation in a try-except to catch disconnects
                try:
                    await websocket.send_text(ws_msg.json())
                    logger.debug(f"Sent WebSocket message: {message['type']} to {websocket.client}")
                except RuntimeError as e: # This catches errors if the socket is already closed
                    logger.warning(f"Failed to send message to {websocket.client}, connection likely closed: {e}")
                    break # Break the sender loop if sending fails
                except Exception as e:
                    logger.error(f"Unexpected error during WebSocket send to {websocket.client}: {e}", exc_info=True)
                    break # Break on other unexpected errors
                
            logger.info(f"Sender task for {websocket.client} finished.")
        except asyncio.CancelledError:
            logger.info(f"Sender task for {websocket.client} was cancelled.")
        except Exception as e:
            logger.error(f"Critical error in sender task for {websocket.client}: {e}", exc_info=True)
        finally:
            # The handle_connection's finally block will handle overall cleanup
            pass

    async def _receiver(self, websocket: WebSocket):
        """Receive messages from client and add to from_frontend_queue"""
        client_info = f"{websocket.client.host}:{websocket.client.port}" if websocket.client else "unknown"
        logger.info(f"Starting receiver for {client_info}")

        try:
            while websocket.client_state == WebSocketState.CONNECTED:
                try:
                    data = await websocket.receive_text()
                    if not data:
                        logger.debug(f"Empty message received from {client_info}")
                        continue
                    logger.debug(f"Received raw WebSocket data from {websocket.client}: {data}")
                    
                    # Your existing message parsing and validation logic
                    try:
                        message_dict = json.loads(data)
                    except json.JSONDecodeError as e:
                        await self._send_error(websocket, f"Invalid JSON: {str(e)}")
                        continue

                    if not isinstance(message_dict, dict):
                        await self._send_error(websocket, "Message must be a JSON object")
                        continue
                        
                    required_fields = ['type', 'data']
                    missing_fields = [field for field in required_fields if field not in message_dict]
                    if missing_fields:
                        await self._send_error(websocket, f"Missing required fields: {', '.join(missing_fields)}")
                        continue

                    # Pydantic validation (adjust as per your WebSocketMessage model's needs)
                    try:
                        message = WebSocketMessage.parse_obj(message_dict) # Use parse_obj for dict, parse_raw for string
                        message.client_id = message.client_id or str(websocket.client) # Ensure client_id is set
                    except ValidationError as e:
                        error_details = "; ".join([f"{err['loc'][0]}: {err['msg']}" for err in e.errors()])
                        await self._send_error(websocket, f"Validation failed: {error_details}")
                        continue

                    # Enqueue validated message to from_frontend_queue
                    queue_msg = {
                        'type': message.type,
                        'data': message.data,
                        'timestamp': message.timestamp,
                        'client_id': message.client_id, # Use validated client_id
                        'processing_path': message_dict.get('processing_path', []),
                        'forwarding_path': message_dict.get('forwarding_path', [])
                    }
                    
                    logger.info(f"Enqueuing valid message of type '{message.type}' from {websocket.client}")
                    await get_from_frontend_queue().enqueue(queue_msg)
                
                except Exception as e: # Catch any errors during receive/processing
                    logger.error(f"Receive/processing error for {websocket.client}: {e}", exc_info=True)
                    # For a receive error, it's often best to break the loop as the connection might be bad
                    break
            logger.info(f"Receiver task for {websocket.client} finished.")
        except asyncio.CancelledError:
            logger.info(f"Receiver task for {websocket.client} was cancelled.")
        except Exception as e: # Catch errors that escape the inner try-except
            logger.error(f"Critical error in receiver task for {websocket.client}: {e}", exc_info=True)
        finally:
            # The handle_connection's finally block will handle overall cleanup
            pass

    async def _send_ack(self, websocket: WebSocket) -> None:
        """Send connection acknowledgment"""
        ack = {
            "type": "connection_ack",
            "status": "connected",
            "timestamp": time.time()
        }
        # Wrap send operation in a try-except in case client disconnects immediately
        try:
            await websocket.send_text(json.dumps(ack))
            self.ack_status[websocket] = True
            logger.info(f"Sent connection_ack to {websocket.client}")
        except RuntimeError as e:
            logger.warning(f"Failed to send connection_ack to {websocket.client}, client already disconnected: {e}")
        except Exception as e:
            logger.error(f"Error sending connection_ack to {websocket.client}: {e}")


    async def _cleanup_connection(self, websocket: WebSocket, client_info: str) -> None:
        """Clean up connection resources"""
        logger.info(f"Starting cleanup for {client_info}")
        
        # Remove from connections set
        self.connections.discard(websocket)
        self.ack_status.pop(websocket, None)
        
        # Check WebSocket state before attempting to close
        if websocket.client_state != WebSocketState.DISCONNECTED:
            try:
                await websocket.close(code=1000)  # 1000 = normal closure
                logger.info(f"Closed WebSocket connection for {client_info}")
            except RuntimeError as e:
                # Already closing/closed
                logger.debug(f"WebSocket for {client_info} was already closing or closed: {e}")
            except Exception as e:
                logger.error(f"Unexpected error closing WebSocket for {client_info}: {e}", exc_info=True)
        else:
            logger.debug(f"WebSocket for {client_info} was already disconnected (client_state: {websocket.client_state})")

        logger.info(f"Connection cleanup completed for {client_info}. Remaining connections: {len(self.connections)}")

    async def _send_error(self, websocket: WebSocket, error_msg: str):
        """Send error response to client"""
        try:
            error_response = {
                "type": "error",
                "message": error_msg,
                "timestamp": time.time()
            }
            if websocket.client_state == WebSocketState.CONNECTED: # Only send if still connected
                await websocket.send_text(json.dumps(error_response))
            else:
                logger.warning(f"Attempted to send error but WebSocket for {websocket.client} was not connected: {error_msg}")
        except Exception as e:
            logger.error(f"Failed to send error message to {websocket.client}: {e}", exc_info=True)

    def get_metrics(self):
        """Get WebSocket metrics"""
        return {
            "connections": len(self.connections),
            "acknowledged_connections": len(self.ack_status)
        }

    async def shutdown(self):
        """Clean shutdown of all connections"""
        logger.info("Initiating WebSocketManager shutdown...")
        for websocket in list(self.connections): # Iterate over a copy as set changes during iteration
            client_info = f"{websocket.client.host}:{websocket.client.port}" if websocket.client else "unknown"
            # Cancel associated tasks before cleaning up the connection
            websocket_id = id(websocket)
            if websocket_id in self.active_tasks:
                for task in self.active_tasks[websocket_id]:
                    if not task.done():
                        task.cancel()
                        try:
                            await task # Await cancellation
                        except asyncio.CancelledError:
                            pass
                del self.active_tasks[websocket_id]
            await self._cleanup_connection(websocket, client_info)
        logger.info("WebSocketManager shutdown complete.")

    # Your handle_message, _handle_command, _handle_data from endpoints.py
    # This logic was duplicated. It should ONLY be in websocket_manager.py
    # or you need to decide which one is responsible for processing.
    # Let's assume handle_message is the primary entry point called by endpoints.py
    # and it uses the helper methods.
    async def handle_message(self, websocket: WebSocket, raw_data: str):
        """Handle incoming WebSocket message from the endpoint."""
        try:
            # Your existing receiver logic essentially does this.
            # We can simplify this if _receiver is always active.
            # But if handle_message is called directly by endpoints.py, it needs its own logic.
            logger.debug(f"Handling message from endpoint: {raw_data}")

            try:
                message_dict = json.loads(raw_data)
            except json.JSONDecodeError:
                await self._send_error(websocket, "Invalid JSON format")
                return

            if not isinstance(message_dict, dict):
                await self._send_error(websocket, "Message must be a JSON object")
                return
                
            required_fields = ['type', 'data']
            missing_fields = [field for field in required_fields if field not in message_dict]
            if missing_fields:
                await self._send_error(websocket, f"Missing required fields: {', '.join(missing_fields)}")
                return
            
            try:
                msg = WebSocketMessage.parse_obj(message_dict) # Use parse_obj for dict
                msg.client_id = msg.client_id or str(websocket.client)
            except ValidationError as e:
                error_details = "; ".join([f"{err['loc'][0]}: {err['msg']}" for err in e.errors()])
                await self._send_error(websocket, f"Validation failed: {error_details}")
                return

            # Process based on message type
            if msg.type == 'command':
                await self._handle_command(msg)
            elif msg.type == 'data': # This would be for generic data, or specialized ones
                await self._handle_data(msg)
            elif msg.type == 'frontend_ready_ack':
                logger.info(f"Frontend ready ACK received from {msg.client_id}. Status: {msg.data.get('message')}")
                # No need to enqueue this to from_frontend_queue if it's just an ACK
                # Unless you have a specific backend processor for ACKs.
                pass # Acknowledge and do nothing further for now
            elif msg.type == 'test_message': # Specific handling for the test message
                logger.info(f"Received test message from frontend: {msg.data.get('text')} from {msg.client_id}")
                # You might want to enqueue this to from_frontend_queue for processing
                await get_from_frontend_queue().enqueue({
                    'type': msg.type,
                    'data': msg.data,
                    'timestamp': msg.timestamp,
                    'client_id': msg.client_id
                })
            else:
                logger.warning(f"Unknown message type received: {msg.type} from {msg.client_id}. Enqueuing to from_frontend_queue.")
                # Enqueue unknown types to from_frontend_queue for general processing
                await get_from_frontend_queue().enqueue({
                    'type': msg.type,
                    'data': msg.data,
                    'timestamp': msg.timestamp,
                    'client_id': msg.client_id
                })

        except Exception as e:
            logger.error(f"Top-level message handling error for {websocket.client}: {e}", exc_info=True)
            await self._send_error(websocket, "Internal server error during message processing")


    async def _handle_command(self, msg: WebSocketMessage):
        """Handle command messages (e.g., start/stop simulation)"""
        command = msg.data.get('command')
        if command == 'start_simulation':
            logger.info(f"Processing start_simulation command from {msg.client_id}")
            await get_simulation_manager().start()
        elif command == 'stop_simulation':
            logger.info(f"Processing stop_simulation command from {msg.client_id}")
            await get_simulation_manager().stop()
        else:
            logger.warning(f"Unknown command received: {command} from {msg.client_id}")
            # You might want to send an error back to the frontend for unknown commands
            # await self._send_error(get_websocket_by_client_id(msg.client_id), f"Unknown command: {command}") # Requires mapping client_id to WebSocket

    async def _handle_data(self, msg: WebSocketMessage):
        """Handle generic data messages from frontend by enqueuing them to from_frontend_queue."""
        logger.info(f"Handling data message from {msg.client_id} (type: {msg.type})")
        await get_from_frontend_queue().enqueue({
            'type': msg.type,
            'data': msg.data,
            'timestamp': msg.timestamp,
            'client_id': msg.client_id
        })
