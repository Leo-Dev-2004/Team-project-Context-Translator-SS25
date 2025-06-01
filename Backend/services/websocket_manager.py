# Backend/services/websocket_manager.py (FIXED)

import asyncio
import json
import logging
import time
import uuid
from pydantic import ValidationError # Added import for Pydantic validation
from fastapi import WebSocket
from fastapi.websockets import WebSocketState
from typing import Dict, Any, Union
from starlette.websockets import WebSocketDisconnect # Corrected placement, ensuring it's imported

from ..queues.shared_queue import get_to_frontend_queue, get_from_frontend_queue, get_dead_letter_queue # Added import for dead_letter_queue
from ..models.message_types import WebSocketMessage # Ensure WebSocketMessage is imported

logger = logging.getLogger(__name__)

class WebSocketManager:
    def __init__(self, from_frontend_queue=None):
        self.connections = set()
        self.ack_status = {}
        self.active_tasks = {} # maps websocket_id to (sender_task, receiver_task)
        self._running = True  # Flag for graceful shutdown
        self.from_frontend_queue = from_frontend_queue

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
            # Prefer model_dump for Pydantic v2, fallback to dict() for v1
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

    async def handle_connection(self, websocket: WebSocket, client_id: str):
        """Handle new WebSocket connection"""
        client_info = self._get_formatted_client_address(websocket) # Use the helper
        websocket_id = id(websocket)

        try:
            # --- CRITICAL FIX: ACCEPT THE WEBSOCKET CONNECTION ---
            await websocket.accept()
            logger.info(f"WebSocket connection accepted for {client_info}")
            # --- END CRITICAL FIX ---

            self.connections.add(websocket)
            logger.info(f"Adding connection: {client_info}. Total connections: {len(self.connections)}")

            await self.send_ack(websocket)

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

            await self.cleanup_connection(websocket, client_info)
            logger.info(f"Cleanup finished for connection: {client_info}. Total connections: {len(self.connections)}")

    async def _sender(self, websocket: WebSocket):
        """Send messages from to_frontend_queue to client"""
        client_info = self._get_formatted_client_address(websocket) # Use the helper
        logger.info(f"Sender task started for {client_info}")
        try:
            while True:
                try:
                    message_dict = await asyncio.wait_for(
                        get_to_frontend_queue().dequeue(),
                        timeout=1.0
                    )
                    # --- ADDED 1-SECOND DELAY ---
                    # await asyncio.sleep(1) # 1-second delay after dequeuing
                    logger.debug(f"WebSocketManager sender dequeued message {message_dict.get('id', 'N/A')} of type '{message_dict.get('type', 'N/A')}'. Delaying for 1s.")
                    # --- END ADDED DELAY ---
                except asyncio.TimeoutError:
                    continue # No message in queue, try again
                except Exception as e:
                    logger.error(f"Error dequeuing message in sender: {str(e)}", exc_info=True)
                    await asyncio.sleep(1) # Backoff on dequeue errors
                    continue

                if message_dict is None:
                    logger.warning("Received None message from queue in sender, stopping sender")
                    break # Queue was likely shut down

                try:
                    # Ensure required fields exist before parsing
                    message_dict.setdefault('id', str(uuid.uuid4()))
                    message_dict.setdefault('timestamp', time.time())
                    # Ensure client_id is correctly formatted if it came from the queue
                    # and was perhaps added by another service.
                    if 'client_id' in message_dict and isinstance(message_dict['client_id'], (list, tuple)):
                        message_dict['client_id'] = f"{message_dict['client_id'][0]}:{message_dict['client_id'][1]}"
                    elif 'client_id' not in message_dict or message_dict['client_id'] is None:
                        message_dict['client_id'] = client_info # Default to current client_info if missing/None

                    ws_msg = WebSocketMessage.parse_obj(message_dict)
                    logger.debug(f"Prepared WebSocket message of type '{ws_msg.type}' for client {client_info}")
                except ValidationError as e:
                    logger.error(f"Invalid message format for sending from queue: {e.errors()}\nOriginal message: {message_dict}")
                    # Send an error message to the client, but discard the malformed one
                    await self.send_error(websocket, "backend_message_validation_failed", f"Backend message invalid: {str(e.errors())}")
                    # Consider sending to dead letter queue if this is a critical message that needs audit
                    continue # Skip sending this malformed message
                except Exception as e:
                    logger.error(f"Unexpected error preparing message in sender: {str(e)}", exc_info=True)
                    continue

                try:
                    if websocket.client_state == WebSocketState.CONNECTED:
                        try:
                            # Using model_dump_json for Pydantic v2, json() for v1
                            json_data = ws_msg.model_dump_json() # Pydantic v2
                        except AttributeError:
                            json_data = ws_msg.json() # Pydantic v1

                        await websocket.send_text(json_data)
                        logger.debug(f"Sent message {ws_msg.id} (type: {ws_msg.type}) to {client_info}")
                    else:
                        logger.warning(f"WebSocket not connected for {client_info}, discarding message {ws_msg.id}. Connection state: {websocket.client_state.name}")
                        break # Exit loop if connection is no longer active
                except RuntimeError as e:
                    logger.warning(f"WebSocket connection error for {client_info} during send: {str(e)}. Assuming disconnection.")
                    break # Exit loop on connection error
                except Exception as e:
                    logger.error(f"Unexpected send error to {client_info}: {str(e)}", exc_info=True)
                    await asyncio.sleep(1) # Backoff on send errors
                    continue

        except asyncio.CancelledError:
            logger.info(f"Sender task for {client_info} was cancelled normally.")
        except Exception as e:
            logger.error(f"Sender task crashed for {client_info}: {str(e)}", exc_info=True)
        finally:
            logger.info(f"Sender task for {client_info} finished.")

    async def _receiver(self, websocket: WebSocket):
        """Receive messages with detailed tracing and robust error handling"""
        client_info = self._get_formatted_client_address(websocket)
        msg_counter = 0

        logger.info(f"Starting receiver for {client_info} with enhanced message tracing")
        
        try:
            while True:
                try:
                    # Log before receiving
                    logger.debug(f"[Receiver {msg_counter}] Waiting for message from {client_info}...")
                    
                    try:
                        data = await websocket.receive_text()
                        logger.debug(f"[Receiver {msg_counter}] Received raw data from {client_info}: {data[:200]}...")  # Truncate long messages
                        msg_counter += 1
                    except Exception as recv_error:
                        logger.error(f"Error receiving message from {client_info}: {str(recv_error)}", exc_info=True)
                        await asyncio.sleep(1)  # Backoff to prevent tight loop
                        continue

                    try:
                        # Detailed parsing and validation logging
                        logger.debug(f"[Receiver {msg_counter}] Parsing JSON from {client_info}")
                        raw_message_dict = json.loads(data)
                        logger.debug(f"[Receiver {msg_counter}] Parsed JSON: {json.dumps(raw_message_dict, indent=2)}")

                        # Handle client_id formatting
                        if 'client_id' in raw_message_dict and isinstance(raw_message_dict['client_id'], (list, tuple)):
                            raw_message_dict['client_id'] = f"{raw_message_dict['client_id'][0]}:{raw_message_dict['client_id'][1]}"
                            logger.debug(f"Reformatted client_id to {raw_message_dict['client_id']}")
                        else:
                            raw_message_dict['client_id'] = client_info
                            logger.debug(f"Using connection client_id: {client_info}")

                        # Validate message structure
                        logger.debug(f"[Receiver {msg_counter}] Validating message structure")
                        message = WebSocketMessage.parse_obj(raw_message_dict)
                        logger.info(f"[Receiver {msg_counter}] Valid message type '{message.type}' from {message.client_id}")

                        # Prepare for queue
                        queue_msg = self._create_queue_message(message, 
                            source='websocket_receiver', 
                            status='received')
                        
                        # Detailed enqueue logging
                        logger.debug(f"[Receiver {msg_counter}] Enqueuing to from_frontend_queue")
                        start_time = time.time()
                        await get_from_frontend_queue().enqueue(queue_msg)
                        enqueue_time = time.time() - start_time

                        if enqueue_time > 0.1:
                            logger.warning(f"Slow enqueue took {enqueue_time:.3f}s for message {message.id}")
                        else:
                            logger.debug(f"Enqueued in {enqueue_time:.3f}s")

                    except json.JSONDecodeError as jde:
                        logger.error(f"Invalid JSON from {client_info}: {str(jde)}. Data: {data[:200]}...", exc_info=True)
                        await self._handle_invalid_message(websocket, client_info, data, 'json_decode_error', str(jde))
                        continue
                    except ValidationError as ve:
                        error_details = "; ".join([f"{err['loc'][0]}: {err['msg']}" for err in ve.errors()])
                        logger.error(f"Validation failed for {client_info}: {error_details}. Data: {data[:200]}...", exc_info=True)
                        await self._handle_invalid_message(websocket, client_info, data, 'validation_error', error_details)
                        continue
                    except Exception as parse_error:
                        logger.error(f"Unexpected parsing error from {client_info}: {str(parse_error)}", exc_info=True)
                        await self._handle_invalid_message(websocket, client_info, data, 'parse_error', str(parse_error))
                        continue

                except WebSocketDisconnect as e:
                    logger.info(f"WebSocket cleanly disconnected from {client_info} (code: {e.code})")
                    break
                except asyncio.CancelledError:
                    logger.info(f"Receiver task for {client_info} cancelled normally")
                    break
                except Exception as e:
                    logger.critical(f"CRITICAL ERROR in receiver for {client_info}: {str(e)}", exc_info=True)
                    await asyncio.sleep(1)  # Prevent tight error loop
                    continue

        except Exception as outer_error:
            logger.critical(f"Receiver task crashed for {client_info}: {str(outer_error)}", exc_info=True)
        finally:
            logger.info(f"Receiver task ended for {client_info}. Processed {msg_counter} messages")

    async def _handle_invalid_message(self, websocket: WebSocket, client_info: str, raw_data: str, error_type: str, error_details: str):
        """Centralized handling for invalid messages"""
        try:
            # Send error response to client
            await self.send_error(websocket, "invalid_message", f"Message rejected: {error_type}")
            
            # Log to dead letter queue
            dlq_entry = {
                'original_raw_data': raw_data,
                'error': error_type,
                'details': error_details,
                'timestamp': time.time(),
                'client_id': client_info,
                'component': 'WebSocketManager._receiver'
            }
            await get_dead_letter_queue().enqueue(dlq_entry)
            logger.debug(f"Invalid message from {client_info} sent to DLQ")
        except Exception as e:
            logger.error(f"Failed to handle invalid message from {client_info}: {str(e)}", exc_info=True)
        except asyncio.CancelledError:
            logger.info(f"Receiver task for {client_info} was cancelled.")
        except Exception as e:
            logger.error(f"Critical error in receiver task for {client_info}: {e}", exc_info=True)
        finally:
            pass # No specific cleanup in receiver, handled by handle_connection finally block

    async def send_ack(self, websocket: WebSocket):
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

    async def cleanup_connection(self, websocket: WebSocket, client_info: str):
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

    async def send_error(self, websocket: WebSocket, error_type: str, error_msg: str):
        """Send error response to client with a specific type."""
        client_info = self._get_formatted_client_address(websocket)
        try:
            error_response = {
                "type": "error",
                "data": {"error_type": error_type, "message": error_msg}, # Include error_type
                "timestamp": time.time(),
                "id": str(uuid.uuid4()),
                "client_id": client_info
            }
            error_ws_message = WebSocketMessage.parse_obj(error_response)
            if websocket.client_state == WebSocketState.CONNECTED:
                try:
                    await websocket.send_text(error_ws_message.model_dump_json()) # Pydantic v2
                except AttributeError:
                    await websocket.send_text(error_ws_message.json()) # Pydantic v1
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
            await self.cleanup_connection(websocket, client_info)
        logger.info("WebSocketManager shutdown complete.")

    async def handle_message(self, websocket: WebSocket, raw_data: str):
        """Handle incoming WebSocket message from the endpoint.
        This method is likely called from your FastAPI endpoint directly.
        It enqueues messages to `from_frontend_queue` for processing.
        """
        client_info = self._get_formatted_client_address(websocket)
        logger.debug(f"Handling message from endpoint: {raw_data} for {client_info}")

        try:
            message_dict = json.loads(raw_data)
        except json.JSONDecodeError:
            await self.send_error(websocket, "invalid_json_format", "Invalid JSON format")
            return

        try:
            if not isinstance(message_dict, dict):
                await self.send_error(websocket, "invalid_message_format", "Message must be a JSON object")
                return

            required_fields = ['type', 'data']
            missing_fields = [field for field in required_fields if field not in message_dict]
            if missing_fields:
                await self.send_error(websocket, "missing_fields", f"Missing required fields: {', '.join(missing_fields)}")
                return

            # --- CRUCIAL FIX FOR CLIENT_ID in handle_message ---
            if 'client_id' in message_dict and isinstance(message_dict['client_id'], (list, tuple)):
                message_dict['client_id'] = f"{message_dict['client_id'][0]}:{message_dict['client_id'][1]}"
            else: # If client_id is missing or not list/tuple, use the actual connection client_info
                message_dict['client_id'] = client_info # Default if missing
            # --- END CRUCIAL FIX ---

            try:
                # Use WebSocketMessage.parse_obj to validate and set defaults (like ID, timestamp)
                msg = WebSocketMessage.parse_obj(message_dict)
            except ValidationError as e:
                error_details = "; ".join([f"{err['loc'][0]}: {err['msg']}" for err in e.errors()])
                await self.send_error(websocket, "message_validation_failed", f"Validation failed: {error_details}")
                # Enqueue to DLQ for messages received via handle_message (endpoint)
                await get_dead_letter_queue().enqueue({
                    'original_raw_data': raw_data,
                    'error': 'endpoint_validation_error',
                    'details': e.errors(),
                    'timestamp': time.time(),
                    'client_id': client_info
                })
                return

            # Use the helper to create the queue message, with appropriate source
            # The client_id in 'msg' is already properly formatted due to the fix above.
            queue_msg = self._create_queue_message(msg, source='http_endpoint', status='received') # Changed source to http_endpoint
            await get_from_frontend_queue().enqueue(queue_msg)
            logger.info(f"Enqueued message of type '{msg.type}' from endpoint for {msg.client_id}")

        except Exception as e:
            logger.error(f"Top-level message handling error for {client_info} in handle_message: {e}", exc_info=True)
            await self.send_error(websocket, "internal_server_error", "Internal server error during message processing")
            await get_dead_letter_queue().enqueue({
                'original_raw_data': raw_data,
                'error': 'endpoint_processing_exception',
                'details': str(e),
                'timestamp': time.time(),
                'client_id': client_info
            })

    async def _handle_command(self, msg: WebSocketMessage):
        """
        Handle command messages (e.g., start/stop simulation).
        NOTE: This method is likely for direct processing if the WebSocketManager
        itself acts on commands, but ideally, commands are forwarded to MessageProcessor.
        If this is called, ensure MessageProcessor isn't also acting on them to avoid duplication.
        """
        command = msg.data.get('command')

        # Ensure client_id is a string here, as per our expectation from _receiver/handle_message
        client_id_str: str = msg.client_id if isinstance(msg.client_id, str) else 'unknown'

        if command == 'start_simulation':
            logger.info(f"Processing start_simulation command from {client_id_str}")
            # Example: Interact with a simulation manager
            # await get_simulation_manager().start(client_id=client_id_str)
        elif command == 'stop_simulation':
            logger.info(f"Processing stop_simulation command from {client_id_str}")
            # Example: Interact with a simulation manager
            # await get_simulation_manager().stop(client_id=client_id_str)
        else:
            logger.warning(f"Unknown command received: {command} from {client_id_str}")

    async def _handle_data(self, msg: WebSocketMessage):
        """
        Handle generic data messages from frontend by enqueuing them to from_frontend_queue.
        NOTE: This is redundant if all messages go through the main queuing mechanism.
        """
        client_id_str: str = msg.client_id if isinstance(msg.client_id, str) else 'unknown'
        logger.info(f"Handling data message from {client_id_str} (type: {msg.type})")
        queue_msg = self._create_queue_message(msg, source='frontend_data', status='processed')
        await get_from_frontend_queue().enqueue(queue_msg)

    async def send_message_to_client(self, client_id: str, message_data: Dict[str, Any]):
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
