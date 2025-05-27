# Backend/services/websocket_manager.py

import asyncio
import json
import logging
import time
import uuid
from pydantic import ValidationError
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
        self._running = True  # Flag for graceful shutdown

    # Helper function to create a standardized message for the internal queue
    def _create_queue_message(self, message: WebSocketMessage, source: str, status: str) -> Dict[str, Any]:
        """Constructs a dictionary formatted for internal MessageQueue usage."""
        
        # Safely convert the WebSocketMessage Pydantic model to a dictionary
        message_as_dict = message.dict(exclude_unset=True)

        # Ensure message_id is a string or generate a new one
        message_id = message_as_dict.get('id')
        if message_id is None:
            message_id = str(message.id) if hasattr(message, 'id') and message.id else str(uuid.uuid4())
        else:
            message_id = str(message_id)

        # Safely get client_id
        client_id_str = message_as_dict.get('client_id', 'unknown')
        if client_id_str is None:
            client_id_str = 'unknown'

        # Get paths directly from message
        processing_path = message_as_dict.get('processing_path', [])
        forwarding_path = message_as_dict.get('forwarding_path', [])

        # Ensure these are lists
        if not isinstance(processing_path, list):
            processing_path = []
        if not isinstance(forwarding_path, list):
            forwarding_path = []

        return {
            'id': message_id,
            'type': message_as_dict['type'],
            'data': message_as_dict['data'],
            'timestamp': message_as_dict.get('timestamp', time.time()),
            'client_id': client_id_str,
            'processing_path': processing_path,
            'forwarding_path': forwarding_path,
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
                try:
                    # Get message from queue with timeout
                    try:
                        message = await asyncio.wait_for(
                            get_to_frontend_queue().dequeue(),
                            timeout=1.0
                        )
                    except asyncio.TimeoutError:
                        # Timeout occurred, check if we should continue
                        continue
                    except Exception as e:
                        logger.error(f"Error dequeuing message: {str(e)}")
                        await asyncio.sleep(1)
                        continue

                    if message is None:
                        logger.warning("Received None message from queue, stopping sender")
                        break
                except Exception as e:
                    logger.error(f"Error dequeuing message: {str(e)}")
                    await asyncio.sleep(1)
                    continue

                if not message:
                    continue

                # Convert queue message to WebSocketMessage
                try:
                    # Ensure required fields exist
                    message.setdefault('id', str(uuid.uuid4()))
                    message.setdefault('timestamp', time.time())
                    
                    # Convert to WebSocketMessage with extra validation
                    ws_msg = WebSocketMessage.parse_obj(message)
                    logger.debug(f"Prepared WebSocket message of type '{ws_msg.type}' for client {websocket.client}")
                except ValidationError as e:
                    logger.error(f"Invalid message format in sender: {e.errors()}\nOriginal message: {message}")
                    # Convert to error message to send to frontend
                    ws_msg = WebSocketMessage(
                        client_id=message.get('client_id', 'unknown'),
                        type="error",
                        data={
                            "error": "invalid_message_format",
                            "details": str(e.errors()),
                            "original_type": message.get('type')
                        },
                        timestamp=time.time()
                    )
                except Exception as e:
                    logger.error(f"Unexpected error preparing message: {str(e)}")
                    continue

                # Send message
                try:
                    if websocket.client_state == WebSocketState.CONNECTED:
                        await websocket.send_text(ws_msg.json())
                        logger.debug(f"Sent message {ws_msg.id} (type: {ws_msg.type}) to {websocket.client}")
                    else:
                        logger.warning(f"WebSocket not connected, discarding message {ws_msg.id}")
                        break
                except RuntimeError as e:
                    logger.warning(f"WebSocket connection error: {str(e)}")
                    break
                except Exception as e:
                    logger.error(f"Unexpected send error: {str(e)}")
                    await asyncio.sleep(1)
                    continue

        except asyncio.CancelledError:
            logger.info(f"Sender task for {websocket.client} was cancelled normally")
        except Exception as e:
            logger.error(f"Sender task crashed: {str(e)}", exc_info=True)
        finally:
            logger.info(f"Sender task for {websocket.client} finished")

    async def _receiver(self, websocket: WebSocket):
        """Receive messages from client and add to from_frontend_queue"""
        logger.info(f"Receiver task started for {websocket.client}")
        try:
            while True:
                try:
                    data = await websocket.receive_text()
                    logger.debug(f"Received raw WebSocket data from {websocket.client}: {data}")
                    
                    try:
                        # Parse and validate using Pydantic model (compatible with both v1 and v2)
                        message = WebSocketMessage.parse_raw(data)
                        message_dict = message.dict()
                        
                        # Ensure data is always a dict
                        if not isinstance(message_dict.get('data'), dict):
                            message_dict['data'] = {}
                        
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
                        logger.error(f"Error processing received message: {e}", exc_info=True)
                        await self._send_error(websocket, "Error processing message")
                        continue
                
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
