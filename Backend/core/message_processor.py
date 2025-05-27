# Backend/services/message_processor.py

import asyncio
import copy
import logging
import time
import uuid # Needed for generating IDs for new messages
from typing import Optional, Dict, Any
from pydantic import ValidationError # Needed for Pydantic model validation
from ..queues.shared_queue import (
    get_to_backend_queue, # Correct input queue for MessageProcessor
    get_to_frontend_queue, # Output queue for responses to frontend
    get_dead_letter_queue # For handling unprocessable messages
)
from ..models.message_types import ProcessingPathEntry, WebSocketMessage # Ensure WebSocketMessage is imported
from ..dependencies import get_simulation_manager # Assuming this dependency is used for commands

logger = logging.getLogger(__name__)

class MessageProcessor:
    def __init__(self):
        self._running = False
        self._processing_task = None # To store the running task
        self._input_queue = None
        self._output_queue = None
        self._dead_letter_queue = None

    async def initialize(self):
        """Sichere Initialisierung mit Queue-Validierung"""
        try:
            # Correct queue assignments based on the overall flow
            self._input_queue = get_to_backend_queue() # Messages from QueueForwarder come here
            self._output_queue = get_to_frontend_queue() # Responses go to WebSocketManager from here
            self._dead_letter_queue = get_dead_letter_queue() # For errors

            if None in (self._input_queue, self._output_queue, self._dead_letter_queue):
                raise RuntimeError("One or more MessageProcessor queues not initialized correctly")

            logger.info("MessageProcessor queues verified and initialized.")
        except Exception as e:
            logger.error(f"Failed to initialize MessageProcessor: {str(e)}", exc_info=True)
            raise

    def _get_input_queue_size(self):
        """Returns the size of the input queue."""
        if self._input_queue:
            return self._input_queue.size()
        return 0

    async def start(self):
        """Starts the main message processing loop as a background task."""
        if not self._running:
            self._running = True
            logger.info("Starting MessageProcessor task.")
            self._processing_task = asyncio.create_task(self._process_messages()) # Renamed to _process_messages
            logger.info("MessageProcessor task created and running in background.")
        else:
            logger.info("MessageProcessor already running.")

    async def _process_messages(self): # Renamed from 'process'
        """Main processing loop with robust error handling"""
        logger.info("MessageProcessor main loop started.")
        
        processed_count = 0
        last_log_time = time.time()
        
        while self._running:
            try:
                if self._input_queue is None:
                    logger.error("MessageProcessor input queue not initialized. Cannot process messages. message_processor; L64")
                    await asyncio.sleep(1)
                    continue

                message = await self._input_queue.dequeue()
                # --- ADDED 1-SECOND DELAY ---
                await asyncio.sleep(1) # 1-second delay after dequeuing
                logger.debug(f"MessageProcessor dequeued message {message.get('id', 'N/A')} of type '{message.get('type', 'N/A')}'. Delaying for 1s.")
                # --- END ADDED DELAY ---

                if message is None:
                    await asyncio.sleep(0.1) # Small sleep if queue is empty
                    continue

                # Process message and get potential response
                processed_and_response_msg = await self._process_single_message(message) # Delegate to new helper

                # If _process_single_message generated a response, it would have enqueued it.
                # This loop just continues to the next message.

                processed_count += 1
                
                # Periodic logging
                if time.time() - last_log_time > 5:
                    logger.info(f"Processed {processed_count} messages in the last 5 seconds.")
                    last_log_time = time.time()
                    processed_count = 0

            except asyncio.CancelledError:
                logger.info("MessageProcessor task was cancelled gracefully.")
                break # Exit the loop on cancellation
            except Exception as e:
                logger.error(f"Error during MessageProcessor main loop: {str(e)}", exc_info=True)
                await asyncio.sleep(1)  # Backoff on errors

        logger.info("MessageProcessor main loop stopped.")

    async def _process_single_message(self, message: Dict) -> None:
        """Process messages with simulation flow tracking"""
        try:
            msg = WebSocketMessage.parse_obj(message)
            logger.debug(f"Processing {msg.type} message from {msg.client_id}")

            # Track processing path
            msg.processing_path.append("MessageProcessor")
            
            if msg.type == "ping":
                response = WebSocketMessage(
                    id=str(uuid.uuid4()),
                    type="pong",
                    data={"original_id": msg.id},
                    timestamp=time.time(),
                    client_id=msg.client_id,
                    processing_path=msg.processing_path,
                    forwarding_path=[]
                )
                await self._output_queue.enqueue(response.dict())

            elif msg.type == "command":
                if msg.data.get("command") == "start_simulation":
                    # Start simulation flow
                    status_msg = WebSocketMessage(
                        id=str(uuid.uuid4()),
                        type="status",
                        data={
                            "status": "starting",
                            "command": "start_simulation"
                        },
                        timestamp=time.time(),
                        client_id=msg.client_id,
                        processing_path=msg.processing_path,
                        forwarding_path=[]
                    )
                    await self._output_queue.enqueue(status_msg.dict())

                    # Simulate processing delay
                    await asyncio.sleep(1)
                    
                    # Send simulation started confirmation
                    started_msg = WebSocketMessage(
                        id=str(uuid.uuid4()),
                        type="status",
                        data={
                            "status": "running",
                            "progress": 0
                        },
                        timestamp=time.time(),
                        client_id=msg.client_id,
                        processing_path=msg.processing_path,
                        forwarding_path=[]
                    )
                    await self._output_queue.enqueue(started_msg.dict())

            # Handle other message types...
        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            await self._dead_letter_queue.enqueue({
                'error': str(e),
                'original': message,
                'timestamp': time.time()
            })
            if not isinstance(message, dict):
                logger.error(f"Invalid message format received by MessageProcessor: Not a dictionary. Message: {message}")
                await self._safe_enqueue(self._dead_letter_queue, {
                    'original_message': message,
                    'error': 'invalid_format_not_dict',
                    'timestamp': time.time()
                })
                return None # No response, message is invalid
                
            # Deep copy to avoid modifying the original message in queue
            processed_message = copy.deepcopy(message)

            # Ensure data field exists and is a dictionary
            if 'data' not in processed_message or not isinstance(processed_message['data'], dict):
                logger.warning(f"Message 'data' field missing or invalid for ID {processed_message.get('id')}. Initializing as empty dict.")
                processed_message['data'] = {}

            # Add processing metadata
            if 'processing_path' not in processed_message or not isinstance(processed_message['processing_path'], list):
                processed_message['processing_path'] = []
            
            new_path_entry_data = {
                'processor': "MessageProcessor",
                'timestamp': time.time(),
                'status': 'completed',
                'completed_at': time.time()
            }
            processed_message['processing_path'].append(new_path_entry_data)
            logger.debug(f"Added processing path for message {processed_message.get('id')}: {new_path_entry_data}")

            # --- Core Message Processing Logic based on 'type' ---
            msg_type = processed_message.get('type')
            client_id = processed_message.get('client_id', 'unknown_client') # Get client_id for responses

            if msg_type == 'command':
                command_name = processed_message['data'].get('command')
                logger.info(f"MessageProcessor: Processing command '{command_name}' from {client_id}")

                if command_name == 'start_simulation':
                    # Call SimulationManager (assuming it has a start method that takes client_id)
                    # if get_simulation_manager().is_ready(): # Example check
                    #     await get_simulation_manager().start(client_id=client_id)
                    # else:
                    #     logger.warning("SimulationManager not ready to start simulation.")

                    response_message_dict = WebSocketMessage(
                        type="status",
                        data={"status": "simulation_started", "message": "Simulation initiated.", "command": command_name},
                        client_id=client_id,
                        # Pass updated processing_path for full trace
                        processing_path=processed_message.get('processing_path', []),
                        forwarding_path=processed_message.get('forwarding_path', []) # Also include forwarding path
                    ).model_dump()
                    logger.info(f"MessageProcessor: Generated 'status: simulation_started' response for {client_id}.")

                elif command_name == 'stop_simulation':
                    # await get_simulation_manager().stop(client_id=client_id)
                    response_message_dict = WebSocketMessage(
                        type="status",
                        data={"status": "simulation_stopped", "message": "Simulation terminated.", "command": command_name},
                        client_id=client_id,
                        processing_path=processed_message.get('processing_path', []),
                        forwarding_path=processed_message.get('forwarding_path', [])
                    ).model_dump()
                    logger.info(f"MessageProcessor: Generated 'status: simulation_stopped' response for {client_id}.")

                else:
                    logger.warning(f"MessageProcessor: Unknown command '{command_name}' from {client_id}. Sending error response.")
                    response_message_dict = WebSocketMessage(
                        type="error",
                        data={"error": "unknown_command", "command": command_name, "message": "Command not recognized."},
                        client_id=client_id,
                        processing_path=processed_message.get('processing_path', []),
                        forwarding_path=processed_message.get('forwarding_path', [])
                    ).model_dump()

            elif msg_type == 'ping':
                logger.info(f"MessageProcessor: Received ping from {client_id}. Responding with pong.")
                response_message_dict = WebSocketMessage(
                    type="pong",
                    data={"message": "pong", "original_timestamp": processed_message.get('timestamp')},
                    client_id=client_id,
                    processing_path=processed_message.get('processing_path', []),
                    forwarding_path=processed_message.get('forwarding_path', [])
                ).model_dump()

            elif msg_type == 'frontend_ready_ack':
                logger.info(f"MessageProcessor: Frontend ready ACK received from {client_id}. Status: {processed_message['data'].get('message')}")
                # No direct response is typically needed for this ACK, but you could send a welcome message if desired.
                # response_message_dict = WebSocketMessage(type="system_info", data={"message": "Welcome to the system!"}, client_id=client_id).model_dump()
                pass # Do nothing, just acknowledge

            else:
                logger.warning(f"MessageProcessor: Unhandled message type: '{msg_type}' from {client_id}. Sending to Dead Letter Queue.")
                await self._safe_enqueue(self._dead_letter_queue, {
                    'original_message': processed_message,
                    'error': 'unhandled_message_type',
                    'timestamp': time.time(),
                    'client_id': client_id # Include client_id in DLQ message
                })
            
            # Enqueue response if generated
            if response_message_dict:
                if not await self._safe_enqueue(self._output_queue, response_message_dict):
                    logger.error(f"Failed to enqueue response message (type: {response_message_dict.get('type')}) to to_frontend_queue for client {client_id}. Sending to DLQ.")
                    await self._safe_enqueue(self._dead_letter_queue, {
                        'original_message': response_message_dict,
                        'error': 'response_enqueue_failed',
                        'timestamp': time.time(),
                        'client_id': client_id
                    })
                else:
                    logger.info(f"Enqueued response type '{response_message_dict.get('type')}' to to_frontend_queue for client {client_id}.")

        except Exception as e:
            logger.error(f"Error processing single message {message.get('id', 'N/A')}: {str(e)}", exc_info=True)
            await self._safe_enqueue(self._dead_letter_queue, {
                'original_message': message,
                'error': 'processing_exception',
                'details': str(e),
                'timestamp': time.time(),
                'client_id': message.get('client_id', 'unknown_client')
            })
        return None # This method doesn't return the message, it enqueues responses

    async def _safe_dequeue(self, queue) -> Optional[Dict]:
        """Thread-safe dequeue with error handling."""
        try:
            return await queue.dequeue() if queue else None
        except Exception as e:
            logger.warning(f"Safe Dequeue failed in MessageProcessor: {str(e)}")
            return None

    async def _safe_enqueue(self, queue, message) -> bool:
        """Thread-safe enqueue with error handling."""
        try:
            if queue:
                await queue.enqueue(message)
                return True
            return False
        except Exception as e:
            logger.warning(f"Safe Enqueue failed in MessageProcessor: {str(e)}")
            return False

    async def stop(self):
        """Graceful shutdown for the MessageProcessor."""
        if self._running:
            self._running = False
            if self._processing_task:
                self._processing_task.cancel()
                try:
                    await self._processing_task # Await for task to finish cancellation
                except asyncio.CancelledError:
                    pass
            logger.info("MessageProcessor shutdown complete.")
        else:
            logger.info("MessageProcessor was not running.")
