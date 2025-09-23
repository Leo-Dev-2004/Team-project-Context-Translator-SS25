# Backend/MessageRouter.py

import asyncio
import logging
import time
import uuid
from typing import Optional

from pydantic import ValidationError

from .models.UniversalMessage import UniversalMessage, ErrorTypes, ProcessingPathEntry
from .core.Queues import queues
from .queues.QueueTypes import AbstractMessageQueue
from .AI.SmallModel import SmallModel
from .dependencies import get_simulation_manager, get_session_manager_instance, get_websocket_manager_instance

logger = logging.getLogger(__name__)

class MessageRouter:
    def __init__(self):
        self._client_incoming_queue: AbstractMessageQueue = queues.incoming
        self._service_outgoing_queue: AbstractMessageQueue = queues.outgoing
        self._websocket_out_queue: AbstractMessageQueue = queues.websocket_out
        
        self._running = False
        self._router_task: Optional[asyncio.Task] = None
        self._small_model: SmallModel = SmallModel()
        self._simulation_manager = get_simulation_manager()
        self._session_manager = get_session_manager_instance()
        self._websocket_manager = get_websocket_manager_instance()

        logger.info("MessageRouter initialized with all dependencies.")

    async def start(self):
        """Starts the message routing process with dual listeners."""
        if not self._running:
            self._running = True
            self._router_task = asyncio.create_task(self._run_message_loops())
            logger.info("MessageRouter started with dual listeners.")

    async def stop(self):
        """Stops the message routing process."""
        # ... (method remains unchanged)
        if self._running:
            self._running = False
            if self._router_task:
                self._router_task.cancel()
                try:
                    await self._router_task
                except asyncio.CancelledError:
                    logger.info("MessageRouter tasks cancelled successfully.")

    async def _run_message_loops(self):
        """Orchestrates the two parallel listener tasks."""
        # ... (method remains unchanged)
        client_listener = asyncio.create_task(self._client_message_listener())
        service_listener = asyncio.create_task(self._service_message_listener())
        await asyncio.gather(client_listener, service_listener)

    async def _client_message_listener(self):
        """Processes messages coming directly from clients (via WebSocket)."""
        # ... (method remains unchanged)
        logger.info("MessageRouter: Listening for messages from clients...")
        while self._running:
            try:
                message = await self._client_incoming_queue.dequeue()
                await self._process_client_message(message)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in client message listener: {e}", exc_info=True)
                await asyncio.sleep(1)

    async def _service_message_listener(self):
        """Processes messages coming from internal services (e.g., SimulationManager)."""
        # ... (method remains unchanged)
        logger.info("MessageRouter: Listening for messages from backend services...")
        while self._running:
            try:
                message = await self._service_outgoing_queue.dequeue()
                await self._route_service_message(message)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in service message listener: {e}", exc_info=True)
                await asyncio.sleep(1)

    async def _process_client_message(self, message: UniversalMessage):
        """Handles logic for a single message from a client."""
        response: Optional[UniversalMessage] = None
        try:
            # Logik zur Verarbeitung der init-Nachrichten
            if message.type == 'frontend.init' or message.type == 'stt.init':
                user_session_id = message.payload.get('user_session_id')
                if self._websocket_manager and user_session_id and message.client_id:
                    self._websocket_manager.associate_user_session(
                        client_id=message.client_id,
                        user_session_id=user_session_id
                    )
                    response = self._create_ack_message(message, f"{message.type} handshake successful.")
                else:
                    response = self._create_error_message(message, ErrorTypes.INVALID_INPUT, "Init message missing user_session_id.")
            
            elif message.type == 'stt.transcription':
                asyncio.create_task(self._small_model.process_message(message))
                response = None  # Response will be handled asynchronously

            elif message.type == 'session.start':
                if self._session_manager and message.client_id:
                    code = self._session_manager.create_session(creator_client_id=message.client_id)
                    if code:
                        response = UniversalMessage(type='session.created', payload={'code': code}, destination=message.client_id, origin='MessageRouter', client_id=message.client_id)
                    else:
                        response = self._create_error_message(message, ErrorTypes.INVALID_ACTION, "Eine Session ist bereits aktiv.")
                else:
                    response = self._create_error_message(message, ErrorTypes.INTERNAL_SERVER_ERROR, "SessionManager nicht verfügbar.")

            elif message.type == 'session.join':
                code_to_join = message.payload.get('code')
                if self._session_manager and code_to_join and message.client_id:
                    success = self._session_manager.join_session(joiner_client_id=message.client_id, code=code_to_join)
                    if success:
                        response = UniversalMessage(type='session.joined', payload={'code': code_to_join}, destination=message.client_id, origin='MessageRouter', client_id=message.client_id)
                    else:
                        response = self._create_error_message(message, ErrorTypes.INVALID_INPUT, "Session-Code ist ungültig.")
                else:
                    response = self._create_error_message(message, ErrorTypes.INVALID_INPUT, "Kein Code angegeben oder SessionManager nicht verfügbar.")

            elif message.type == 'ping':
                response = self._create_pong_message(message)

            else:
                response = self._create_error_message(message, ErrorTypes.UNKNOWN_MESSAGE_TYPE, f"Unknown message type: '{message.type}'")

            if response:
                await self._websocket_out_queue.enqueue(response)

        except Exception as e:
            logger.error(f"Error processing client message {message.id}: {e}", exc_info=True)
            if message:
                error_response = self._create_error_message(message, ErrorTypes.INTERNAL_SERVER_ERROR, str(e))
                await self._websocket_out_queue.enqueue(error_response)

    async def _route_service_message(self, message: UniversalMessage):
        """Routes a message from an internal service to the appropriate clients."""
        # ... (method remains unchanged)
        try:
            if message.destination == "frontend":
                message.destination = "all_frontends"
                await self._websocket_out_queue.enqueue(message)
            else:
                logger.warning(f"Unhandled service message destination: '{message.destination}'")
        except Exception as e:
            logger.error(f"Error routing service message {message.id}: {e}", exc_info=True)

    # ### Helper Methods ###
    def _create_ack_message(self, origin_msg: UniversalMessage, text: str) -> UniversalMessage:
        return UniversalMessage(
            type='system.acknowledgement',
            payload={'message': text, 'original_message_id': origin_msg.id},
            destination=origin_msg.client_id,
            origin='MessageRouter',
            client_id=origin_msg.client_id
        )

    def _create_error_message(self, origin_msg: UniversalMessage, err_type: ErrorTypes, text: str) -> UniversalMessage:
        return UniversalMessage(
            type=err_type.value,
            payload={'error': text, 'original_message_id': origin_msg.id},
            destination=origin_msg.client_id,
            origin='MessageRouter',
            client_id=origin_msg.client_id
        )
        
    def _create_pong_message(self, origin_msg: UniversalMessage) -> UniversalMessage:
        return UniversalMessage(
            type='pong',
            payload={'timestamp': time.time()},
            destination=origin_msg.client_id,
            origin='MessageRouter',
            client_id=origin_msg.client_id
        )