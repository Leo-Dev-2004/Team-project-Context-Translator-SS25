# Backend/services/websocket_manager.py

import asyncio
import json
import logging
import time
import uuid
from fastapi import WebSocket
from fastapi.websockets import WebSocketState
from pydantic import ValidationError
from typing import Dict, Any, Union # Added Union for send_personal_message

from ..queues.shared_queue import get_to_frontend_queue, get_from_frontend_queue
from ..models.message_types import WebSocketMessage
from ..dependencies import get_simulation_manager

logger = logging.getLogger(__name__)

class WebSocketManager:
    def __init__(self):
        self.connections = set()
        self.ack_status = {}
        self.active_tasks = {} # maps websocket_id to (sender_task, receiver_task)

    # Helper function to create a standardized message for the internal queue
    def _create_queue_message(self, message: WebSocketMessage, source: str, status: str) -> Dict[str, Any]:
        """Constructs a dictionary formatted for internal MessageQueue usage.
        Ensures all required fields for queue validation are present.
        """
        # Ensure message.id is a string or generate a new one
        message_id = str(message.id) if hasattr(message, 'id') and message.id else str(uuid.uuid4())
        
        # Ensure client_id is always a string. If msg.client_id is Optional[str],
        # this safely converts None to 'unknown'.
        client_id_str = message.client_id if message.client_id is not None else 'unknown'

        # Safely get trace data from Pydantic model
        trace_data = {}
        if hasattr(message, '_trace'):
            # Convert to dict if it's a Pydantic model
            trace_data = message._trace if message._trace is not None else {}
            if trace_data is None:
                trace_data = {}

        return {
            'id': message_id,
            'type': message.type,
            'data': message.data,
            'timestamp': message.timestamp,
            'client_id': client_id_str,
            'processing_path': trace_data.get('processing_path', []),
            'forwarding_path': trace_data.get('forwarding_path', []),
            'source': source,
            'status': status
        }

    async def handle_connection(self, websocket: WebSocket):
        """Handle new WebSocket connection"""
        client = websocket.client
        client_info = f"{client.host}:{client.port}" if client else "unknown"

        websocket_id = id(websocket)

        try:
            self.connections.add(websocket)
            logger.info(f"Adding connection: {client_info}. Total connections: {len(self.connections)}")

            await self._send_ack(websocket)

            sender_task = asyncio.create_task(self._sender(websocket))
            receiver_task = asyncio.create_task(self._receiver(websocket))

            self.active_tasks[websocket_id] = (sender_task, receiver_task)

            await asyncio.gather(sender_task, receiver_task)

        except Exception as e:
            logger.error(f"Connection lifetime error for {client_info}: {e}", exc_info=True)
        finally:
            logger.info(f"Initiating cleanup for connection: {client_info}")
            if websocket_id in self.active_tasks:
                for task in self.active_tasks[websocket_id]:
                    if not task.done():
                        task.cancel()
                        try:
                            await task
                        except asyncio.CancelledError:
                            pass
                del self.active_tasks[websocket_id]
            
            await self._cleanup_connection(websocket, client_info)
            logger.info(f"Cleanup finished for connection: {client_info}. Total connections: {len(self.connections)}")

    async def _sender(self, websocket: WebSocket):
        """Send messages from to_frontend_queue to client"""
        logger.info(f"Sender task started for {websocket.client}")
        try:
            while True:
                # This dequeue will return a dictionary that was formatted by _create_queue_message
                message = await get_to_frontend_queue().dequeue()
                if not message:
                    continue
                    
                # The message from the queue should already be a dict conforming to WebSocketMessage
                # We can directly instantiate WebSocketMessage from the dequeued dictionary
                try:
                    # Create a WebSocketMessage from the dequeued dict (it should have all fields)
                    ws_msg = WebSocketMessage(**message)
                except ValidationError as e:
                    logger.error(f"Validation error creating WebSocketMessage from dequeued message in sender: {e.errors()} Message: {message}")
                    continue # Skip sending invalid message

                try:
                    await websocket.send_text(ws_msg.json()) # Use .json() for Pydantic v1.x
                    logger.debug(f"Sent WebSocket message: {message['type']} to {websocket.client}")
                except RuntimeError as e:
                    logger.warning(f"Failed to send message to {websocket.client}, connection likely closed: {e}")
                    break
                except Exception as e:
                    logger.error(f"Unexpected error during WebSocket send to {websocket.client}: {e}", exc_info=True)
                    break
                
            logger.info(f"Sender task for {websocket.client} finished.")
        except asyncio.CancelledError:
            logger.info(f"Sender task for {websocket.client} was cancelled.")
        except Exception as e:
            logger.error(f"Critical error in sender task for {websocket.client}: {e}", exc_info=True)
        finally:
            pass

    async def _receiver(self, websocket: WebSocket):
        """Receive messages from client and add to from_frontend_queue"""
        logger.info(f"Receiver task started for {websocket.client}")
        try:
            while True:
                try:
                    data = await websocket.receive_text()
                    logger.debug(f"Received raw WebSocket data from {websocket.client}: {data}")
                    
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

                    try:
                        message = WebSocketMessage.parse_obj(message_dict)
                        # Ensure client_id is set if not provided by the client, using websocket info
                        # This line guarantees message.client_id is a string (or 'unknown') after this point
                        message.client_id = message.client_id if message.client_id is not None else str(websocket.client) 
                    except ValidationError as e:
                        error_details = "; ".join([f"{err['loc'][0]}: {err['msg']}" for err in e.errors()])
                        await self._send_error(websocket, f"Validation failed: {error_details}")
                        continue

                    # Use the helper to create the queue message, with source='websocket'
                    queue_msg = self._create_queue_message(message, source='websocket', status='pending')
                    
                    logger.info(f"Enqueuing valid message of type '{message.type}' from {websocket.client}")
                    await get_from_frontend_queue().enqueue(queue_msg)
                
                except Exception as e:
                    logger.error(f"Receive/processing error for {websocket.client}: {e}", exc_info=True)
                    break # Break the loop on error to prevent continuous failures
            logger.info(f"Receiver task for {websocket.client} finished.")
        except asyncio.CancelledError:
            logger.info(f"Receiver task for {websocket.client} was cancelled.")
        except Exception as e:
            logger.error(f"Critical error in receiver task for {websocket.client}: {e}", exc_info=True)
        finally:
            pass

    async def _send_ack(self, websocket: WebSocket):
        """Send connection acknowledgment"""
        ack = {
            "type": "connection_ack",
            "data": {
                "status": "connected"
            },
            "timestamp": time.time()
        }
        try:
            await websocket.send_text(json.dumps(ack))
            self.ack_status[websocket] = True
            logger.info(f"Sent connection_ack to {websocket.client}")
        except RuntimeError as e:
            logger.warning(f"Failed to send connection_ack to {websocket.client}, client already disconnected: {e}")
        except Exception as e:
            logger.error(f"Error sending connection_ack to {websocket.client}: {e}")

    async def _cleanup_connection(self, websocket: WebSocket, client_info: str):
        """Clean up connection resources"""
        logger.info(f"Starting cleanup for {client_info}")
        
        self.connections.discard(websocket)
        self.ack_status.pop(websocket, None)
        
        if websocket.client_state != WebSocketState.DISCONNECTED:
            try:
                await websocket.close(code=1000)
                logger.info(f"Closed WebSocket connection for {client_info}")
            except RuntimeError as e:
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
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.send_text(json.dumps(error_response))
            else:
                logger.warning(f"Attempted to send error but WebSocket for {websocket.client} was not connected: {error_response}")
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
        for websocket in list(self.connections):
            client_info = f"{websocket.client.host}:{websocket.client.port}" if websocket.client else "unknown"
            websocket_id = id(websocket)
            if websocket_id in self.active_tasks:
                for task in self.active_tasks[websocket_id]:
                    if not task.done():
                        task.cancel()
                        try:
                            await task
                        except asyncio.CancelledError:
                            pass
                del self.active_tasks[websocket_id]
            await self._cleanup_connection(websocket, client_info)
        logger.info("WebSocketManager shutdown complete.")

    async def handle_message(self, websocket: WebSocket, raw_data: str):
        """Handle incoming WebSocket message from the endpoint.
        NOTE: If _receiver is always active and enqueues messages,
        this method might represent a duplicate processing path or
        should be refactored to be called by a MessageProcessor service
        that dequeues from `from_frontend_queue`.
        """
        logger.debug(f"Handling message from endpoint: {raw_data}")

        try:
            message_dict = json.loads(raw_data)
        except json.JSONDecodeError:
            await self._send_error(websocket, "Invalid JSON format")
            return

        try:
            if not isinstance(message_dict, dict):
                await self._send_error(websocket, "Message must be a JSON object")
                return
                
            required_fields = ['type', 'data']
            missing_fields = [field for field in required_fields if field not in message_dict]
            if missing_fields:
                await self._send_error(websocket, f"Missing required fields: {', '.join(missing_fields)}")
                return
            
            try:
                msg = WebSocketMessage.parse_obj(message_dict)
                # Ensure client_id is set if not provided by the client, using websocket info
                msg.client_id = msg.client_id if msg.client_id is not None else str(websocket.client) 
                # Pylance is now satisfied because msg.client_id is guaranteed to be a str here.
            except ValidationError as e:
                error_details = "; ".join([f"{err['loc'][0]}: {err['msg']}" for err in e.errors()])
                await self._send_error(websocket, f"Validation failed: {error_details}")
                return

            # Process based on message type
            if msg.type == 'command':
                # Pass msg.client_id directly. It's already guaranteed to be a string.
                await self._handle_command(msg)
            elif msg.type == 'data':
                await self._handle_data(msg)
            elif msg.type == 'frontend_ready_ack':
                logger.info(f"Frontend ready ACK received from {msg.client_id}. Status: {msg.data.get('message')}")
                pass
            elif msg.type == 'test_message':
                logger.info(f"Received test message from frontend: {msg.data.get('text')} from {msg.client_id}")
                # Use the helper to create the queue message for 'test_message'
                queue_msg = self._create_queue_message(msg, source='frontend_test_button', status='received')
                await get_from_frontend_queue().enqueue(queue_msg)
            else:
                logger.warning(f"Unknown message type received: {msg.type} from {msg.client_id}. Enqueuing to from_frontend_queue.")
                # Use the helper to create the queue message for unknown types
                queue_msg = self._create_queue_message(msg, source='unknown_frontend_type', status='pending')
                await get_from_frontend_queue().enqueue(queue_msg)

        except Exception as e:
            logger.error(f"Top-level message handling error for {websocket.client}: {e}", exc_info=True)
            await self._send_error(websocket, "Internal server error during message processing")

    async def _handle_command(self, msg: WebSocketMessage):
        """Handle command messages (e.g., start/stop simulation)"""
        command = msg.data.get('command')
        
        # --- FIX STARTS HERE ---
        # Explicitly tell Pylance that msg.client_id is a string at this point.
        # This assert statement acts as a guarantee for the type checker.
        assert msg.client_id is not None, "client_id should not be None at this stage"
        
        # Now, msg.client_id is guaranteed to be a str for Pylance.
        # You can optionally assign it to a new variable with a str type hint for even more clarity,
        # but it's not strictly necessary after the assert.
        client_id_str: str = msg.client_id 
        # --- FIX ENDS HERE ---

        if command == 'start_simulation':
            logger.info(f"Processing start_simulation command from {client_id_str}")
            # Pass the explicitly typed string
            await get_simulation_manager().start(client_id=client_id_str)
        elif command == 'stop_simulation':
            logger.info(f"Processing stop_simulation command from {client_id_str}")
            # Do the same for stop_simulation if its client_id parameter is also 'str'
            await get_simulation_manager().stop(client_id=client_id_str)
        else:
            logger.warning(f"Unknown command received: {command} from {client_id_str}")



    async def _handle_data(self, msg: WebSocketMessage):
        """Handle generic data messages from frontend by enqueuing them to from_frontend_queue."""
        logger.info(f"Handling data message from {msg.client_id} (type: {msg.type})")
        # Use the helper to create the queue message for generic data
        queue_msg = self._create_queue_message(msg, source='frontend_data', status='processed')
        await get_from_frontend_queue().enqueue(queue_msg)
