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
        self._processing_task = None
        # Initialize queues directly
        self._input_queue = get_from_frontend_queue()
        self._output_queue = get_to_frontend_queue()
        self._dead_letter_queue = get_dead_letter_queue()
        
        # Validate queues
        if None in (self._input_queue, self._output_queue, self._dead_letter_queue):
            raise RuntimeError("MessageProcessor queues not initialized correctly")

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

    async def start(self):
        """Starts the main message processing loop as a background task."""
        if not self._running:
            self._running = True
            logger.info("Starting MessageProcessor task.")
            self._processing_task = asyncio.create_task(self._process_messages()) # Renamed to _process_messages
            logger.info("MessageProcessor task created and running in background.")
        else:
            logger.info("MessageProcessor already running.")

    async def _process_messages(self):
        """Main message processing loop"""
        logger.info("Starting MessageProcessor main loop")
        
        while self._running:
            try:
                message = await self._input_queue.dequeue()
                if message:
                    await self._process_single_message(message)
                else:
                    await asyncio.sleep(0.1)  # Small delay if queue is empty
                    
            except asyncio.CancelledError:
                logger.info("MessageProcessor stopped by cancellation")
                break
            except Exception as e:
                logger.error(f"Error in processing loop: {e}", exc_info=True)
                await asyncio.sleep(1)  # Backoff on errors
                
        logger.info("MessageProcessor main loop ended")

    async def _process_single_message(self, message: Dict) -> None:
        """Process a single message with proper command handling"""
        try:
            if not isinstance(message, dict):
                logger.error("Invalid message format")
                await self._dead_letter_queue.enqueue({
                    'error': 'invalid_message_format',
                    'original': message
                })
                return

            msg_type = message.get('type')
            client_id = message.get('client_id', 'unknown')

            if msg_type == 'command':
                command = message.get('data', {}).get('command')
                logger.info(f"Processing command: {command} from {client_id}")

                if command == 'start_simulation':
                    # Get simulation manager instance
                    manager = get_simulation_manager()
                    await manager.start(client_id=client_id)
                    
                    # Send response
                    response = {
                        'type': 'simulation_status',
                        'data': {
                            'status': 'started',
                            'client_id': client_id
                        },
                        'processing_path': message.get('processing_path', []) + ['message_processor']
                    }
                    await self._output_queue.enqueue(response)

                elif command == 'stop_simulation':
                    manager = get_simulation_manager()
                    await manager.stop(client_id=client_id)
                    
                    response = {
                        'type': 'simulation_status', 
                        'data': {
                            'status': 'stopped',
                            'client_id': client_id
                        },
                        'processing_path': message.get('processing_path', []) + ['message_processor']
                    }
                    await self._output_queue.enqueue(response)

            # Handle other message types if needed
            else:
                logger.debug(f"Forwarding message of type {msg_type}")
                await self._output_queue.enqueue(message)

        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)
            await self._dead_letter_queue.enqueue({
                'error': str(e),
                'original': message,
                'timestamp': time.time()
            })
        """Nachrichtenverarbeitungslogik für eine einzelne Nachricht"""
        response_message_dict = None # Initialize response to None

        try:
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
