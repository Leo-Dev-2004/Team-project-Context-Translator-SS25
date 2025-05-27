import asyncio
import json
import logging
import time
import uuid
from pydantic import ValidationError
from fastapi import WebSocket
from fastapi.websockets import WebSocketState
from pydantic import ValidationError
from typing import Dict, Any, Union 
from starlette.websockets import WebSocketDisconnect # <--- Add this line

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

    # Helper to get the formatted client address string
    def _get_formatted_client_address(self, websocket: WebSocket) -> str:
        client = websocket.client
        if client and hasattr(client, 'host') and hasattr(client, 'port'):
            return f"{client.host}:{client.port}"
        return "unknown"

    # Helper function to create a standardized message for the internal queue
    def _create_queue_message(self, message: WebSocketMessage, source: str, status: str) -> Dict[str, Any]:
        """Constructs a dictionary formatted for internal MessageQueue usage."""
        
        # Safely convert the WebSocketMessage Pydantic model to a dictionary
        # Use model_dump for Pydantic v2, or dict() for Pydantic v1
        try:
            message_as_dict = message.model_dump(exclude_unset=True) # Pydantic v2
        except AttributeError:
            message_as_dict = message.dict(exclude_unset=True) # Pydantic v1

        # Ensure message_id is a string or generate a new one
        message_id = message_as_dict.get('id')
        if message_id is None:
            message_id = str(message.id) if hasattr(message, 'id') and message.id else str(uuid.uuid4())
        else:
            message_id = str(message_id)

        # Safely get client_id, ensuring it's a string, or 'unknown'
        client_id_str = message_as_dict.get('client_id')
        if not isinstance(client_id_str, str) or client_id_str is None:
            # If client_id was not a string or was None from the message, default to 'unknown'
            # Note: This helper doesn't have access to the websocket object,
            # so it can't format the client address here directly.
            # The caller must ensure client_id is correctly set before calling this.
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
            'client_id': client_id_str, # This client_id should already be formatted correctly by the caller
            'processing_path': processing_path,
            'forwarding_path': forwarding_path,
            'source': source,
            'status': status
        }

    async def handle_connection(self, websocket: WebSocket):
        """Handle new WebSocket connection"""
        client_info = self._get_formatted_client_address(websocket) # Use the helper
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
        client_info = self._get_formatted_client_address(websocket) # Use the helper
        logger.info(f"Sender task started for {client_info}")
        try:
            while True:
                try:
                    message = await asyncio.wait_for(
                        get_to_frontend_queue().dequeue(),
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue
                except Exception as e:
                    logger.error(f"Error dequeuing message: {str(e)}")
                    await asyncio.sleep(1)
                    continue

                if message is None:
                    logger.warning("Received None message from queue, stopping sender")
                    break

                if not message:
                    continue

                try:
                    # Ensure required fields exist before parsing
                    message.setdefault('id', str(uuid.uuid4()))
                    message.setdefault('timestamp', time.time())
                    # Ensure client_id is correctly formatted if it came from the queue
                    # and was perhaps added by another service.
                    if 'client_id' in message and isinstance(message['client_id'], (list, tuple)):
                        message['client_id'] = f"{message['client_id'][0]}:{message['client_id'][1]}"
                    elif 'client_id' not in message or message['client_id'] is None:
                        message['client_id'] = client_info # Default to current client_info if missing/None


                    ws_msg = WebSocketMessage.parse_obj(message)
                    logger.debug(f"Prepared WebSocket message of type '{ws_msg.type}' for client {client_info}")
                except ValidationError as e:
                    logger.error(f"Invalid message format in sender: {e.errors()}\nOriginal message: {message}")
                    ws_msg = WebSocketMessage(
                        client_id=message.get('client_id', client_info), # Use client_info if original client_id is bad
                        type="error",
                        data={
                            "error": "invalid_message_format",
                            "details": str(e.errors()),
                            "original_type": message.get('type')
                        },
                        timestamp=time.time(),
                        id=str(uuid.uuid4()) # Ensure ID for error messages
                    )
                except Exception as e:
                    logger.error(f"Unexpected error preparing message in sender: {str(e)}", exc_info=True)
                    continue

                try:
                    if websocket.client_state == WebSocketState.CONNECTED:
                        try:
                            # Using model_dump_json for Pydantic v2, json() for v1
                            json_data = ws_msg.model_dump_json()
                        except AttributeError:
                            json_data = ws_msg.json()
                            
                        await websocket.send_text(json_data)
                        logger.debug(f"Sent message {ws_msg.id} (type: {ws_msg.type}) to {client_info}")
                    else:
                        logger.warning(f"WebSocket not connected for {client_info}, discarding message {ws_msg.id}")
                        break
                except RuntimeError as e:
                    logger.warning(f"WebSocket connection error for {client_info}: {str(e)}")
                    break
                except Exception as e:
                    logger.error(f"Unexpected send error to {client_info}: {str(e)}", exc_info=True)
                    await asyncio.sleep(1)
                    continue

        except asyncio.CancelledError:
            logger.info(f"Sender task for {client_info} was cancelled normally")
        except Exception as e:
            logger.error(f"Sender task crashed for {client_info}: {str(e)}", exc_info=True)
        finally:
            logger.info(f"Sender task for {client_info} finished")

    async def _receiver(self, websocket: WebSocket):
        """Receive messages from client and add to from_frontend_queue"""
        client_info = self._get_formatted_client_address(websocket) # Use the helper
        logger.info(f"Receiver task started for {client_info}")
        try:
            while True:
                try:
                    data = await websocket.receive_text()
                    logger.debug(f"Received raw WebSocket data from {client_info}: {data}")
                    
                    try:
                        # Parse raw JSON data
                        parsed_data = json.loads(data)
                        
                        # Validate and enrich using WebSocketMessage model
                        websocket_msg = WebSocketMessage(
                            **parsed_data,
                            client_id=client_info  # Use the already formatted client_info
                        )
                        
                        # Convert to dict for queue
                        queue_msg = websocket_msg.dict()
                        
                        # Ensure data is always a dict
                        if not isinstance(queue_msg.get('data'), dict):
                            queue_msg['data'] = {}

                        logger.info(f"Enqueuing valid message of type '{queue_msg['type']}' from {client_info}")
                        await get_from_frontend_queue().enqueue(queue_msg)

                    except ValidationError as e:
                        error_details = "; ".join([f"{err['loc'][0]}: {err['msg']}" for err in e.errors()])
                        logger.error(f"Validation error for incoming WebSocket message from {client_info}: {error_details}. Raw data: {data}")
                        await self._send_error(websocket, f"Validation failed: {error_details}")
                        continue
                    except json.JSONDecodeError as jde: 
                        logger.error(f"JSON decode error for incoming WebSocket message from {client_info}: {jde}. Raw data: {data}")
                        await self._send_error(websocket, "Invalid JSON format")
                        continue
                    except Exception as e:
                        logger.error(f"Error processing received message from {client_info}: {e}", exc_info=True)
                        await self._send_error(websocket, "Error processing message")
                        continue
                
                except WebSocketDisconnect as e: 
                    logger.info(f"WebSocket disconnected from {client_info} while receiving: Code {e.code}")
                    break 
                except Exception as e: # Catch other potential receive errors
                    logger.error(f"Receive error for {client_info}: {e}", exc_info=True)
                    break 
            logger.info(f"Receiver task for {client_info} finished.")
        except asyncio.CancelledError:
            logger.info(f"Receiver task for {client_info} was cancelled.")
        except Exception as e:
            logger.error(f"Critical error in receiver task for {client_info}: {e}", exc_info=True)
        finally:
            pass

    async def _send_ack(self, websocket: WebSocket):
        """Send connection acknowledgment"""
        client_info = self._get_formatted_client_address(websocket) # Use the helper
        ack = {
            "type": "connection_ack",
            "data": {
                "status": "connected",
                "client_id": client_info # Ensure ack also uses formatted client_id
            },
            "id": str(uuid.uuid4()), # Added ID for ack messages
            "timestamp": time.time()
        }
        try:
            ack_ws_message = WebSocketMessage.parse_obj(ack) # Validate ack message through Pydantic
            try:
                await websocket.send_text(ack_ws_message.model_dump_json()) # Pydantic v2
            except AttributeError:
                await websocket.send_text(ack_ws_message.json()) # Pydantic v1

            self.ack_status[websocket] = True
            logger.info(f"Sent connection_ack to {client_info}")
        except RuntimeError as e:
            logger.warning(f"Failed to send connection_ack to {client_info}, client already disconnected: {e}")
        except ValidationError as e:
            logger.error(f"Validation error creating ack message for {client_info}: {e.errors()}")
        except Exception as e:
            logger.error(f"Error sending connection_ack to {client_info}: {e}")

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
        client_info = self._get_formatted_client_address(websocket)
        try:
            error_response = {
                "type": "error",
                "data": {"message": error_msg},
                "timestamp": time.time(),
                "id": str(uuid.uuid4()),
                "client_id": client_info
            }
            error_ws_message = WebSocketMessage.parse_obj(error_response)
            if websocket.client_state == WebSocketState.CONNECTED:
                try:
                    await websocket.send_text(error_ws_message.model_dump_json())
                except AttributeError:
                    await websocket.send_text(error_ws_message.json())
            else:
                logger.warning(f"Attempted to send error but WebSocket for {client_info} was not connected: {error_response}")
        except Exception as e:
            logger.error(f"Failed to send error message to {client_info}: {e}", exc_info=True)

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
            client_info = self._get_formatted_client_address(websocket)
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
        This method is likely called from your API endpoint directly.
        It should probably enqueue messages to `from_frontend_queue`
        for processing by `MessageProcessor`, rather than directly handling commands.
        """
        client_info = self._get_formatted_client_address(websocket)
        logger.debug(f"Handling message from endpoint: {raw_data} for {client_info}")

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
            
            # --- CRUCIAL FIX FOR CLIENT_ID in handle_message ---
            if 'client_id' in message_dict:
                if isinstance(message_dict['client_id'], (list, tuple)):
                    message_dict['client_id'] = f"{message_dict['client_id'][0]}:{message_dict['client_id'][1]}"
                elif not isinstance(message_dict['client_id'], str):
                    message_dict['client_id'] = str(message_dict['client_id'])
            else:
                message_dict['client_id'] = client_info # Default if missing
            # --- END CRUCIAL FIX ---

            try:
                msg = WebSocketMessage.parse_obj(message_dict)
            except ValidationError as e:
                error_details = "; ".join([f"{err['loc'][0]}: {err['msg']}" for err in e.errors()])
                await self._send_error(websocket, f"Validation failed: {error_details}")
                return

            # Use the helper to create the queue message, with appropriate source
            # The client_id in 'msg' is already properly formatted due to the fix above.
            queue_msg = self._create_queue_message(msg, source='frontend_endpoint', status='received')
            await get_from_frontend_queue().enqueue(queue_msg)
            logger.info(f"Enqueued message of type '{msg.type}' from endpoint for {msg.client_id}")

        except Exception as e:
            logger.error(f"Top-level message handling error for {client_info}: {e}", exc_info=True)
            await self._send_error(websocket, "Internal server error during message processing")

    async def _handle_command(self, msg: WebSocketMessage):
        """Handle command messages (e.g., start/stop simulation)"""
        command = msg.data.get('command')
        
        # Ensure client_id is a string here, as per our expectation from _receiver/handle_message
        client_id_str: str = msg.client_id if isinstance(msg.client_id, str) else 'unknown'

        if command == 'start_simulation':
            logger.info(f"Processing start_simulation command from {client_id_str}")
            await get_simulation_manager().start(client_id=client_id_str)
        elif command == 'stop_simulation':
            logger.info(f"Processing stop_simulation command from {client_id_str}")
            await get_simulation_manager().stop(client_id=client_id_str)
        else:
            logger.warning(f"Unknown command received: {command} from {client_id_str}")

    async def _handle_data(self, msg: WebSocketMessage):
        """Handle generic data messages from frontend by enqueuing them to from_frontend_queue."""
        client_id_str: str = msg.client_id if isinstance(msg.client_id, str) else 'unknown'
        logger.info(f"Handling data message from {client_id_str} (type: {msg.type})")
        queue_msg = self._create_queue_message(msg, source='frontend_data', status='processed')
        await get_from_frontend_queue().enqueue(queue_msg)

    # Added for completeness, assuming send_personal_message is needed somewhere
    async def send_personal_message(self, message_data: Dict[str, Any], client_id: str):
        """Sends a message directly to a specific client by its client_id (host:port)."""
        logger.info(f"Attempting to send personal message to client: {client_id}")
        target_websocket = None
        for ws in self.connections:
            if self._get_formatted_client_address(ws) == client_id:
                target_websocket = ws
                break

        if target_websocket:
            try:
                # Ensure the message_data has required fields for WebSocketMessage
                message_data.setdefault('id', str(uuid.uuid4()))
                message_data.setdefault('timestamp', time.time())
                message_data.setdefault('client_id', client_id) # Ensure client_id is set
                
                ws_msg = WebSocketMessage.parse_obj(message_data)
                
                if target_websocket.client_state == WebSocketState.CONNECTED:
                    try:
                        await target_websocket.send_text(ws_msg.model_dump_json())
                    except AttributeError:
                        await target_websocket.send_text(ws_msg.json())
                    logger.info(f"Successfully sent personal message to {client_id} (type: {ws_msg.type})")
                else:
                    logger.warning(f"Target WebSocket for {client_id} is not connected. Message not sent.")
            except ValidationError as e:
                logger.error(f"Validation error for personal message to {client_id}: {e.errors()}. Original data: {message_data}")
            except Exception as e:
                logger.error(f"Error sending personal message to {client_id}: {e}", exc_info=True)
        else:
            logger.warning(f"Client {client_id} not found in active connections. Message not sent.")
