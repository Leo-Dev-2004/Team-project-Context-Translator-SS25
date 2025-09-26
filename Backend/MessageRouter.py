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
from .dependencies import get_session_manager_instance, get_websocket_manager_instance

logger = logging.getLogger(__name__)

class MessageRouter:
    def __init__(self):
        self._client_incoming_queue: AbstractMessageQueue = queues.incoming
        self._service_outgoing_queue: AbstractMessageQueue = queues.outgoing
        self._websocket_out_queue: AbstractMessageQueue = queues.websocket_out
        
        self._running = False
        self._router_task: Optional[asyncio.Task] = None
        self._small_model: SmallModel = SmallModel()
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
                # Block empty transcriptions before passing to SmallModel
                transcribed_text = message.payload.get("text", "").strip()
                if not transcribed_text:
                    logger.warning(f"MessageRouter: Blocked empty transcription from client {message.client_id}")
                    response = self._create_error_message(message, ErrorTypes.INVALID_INPUT, "Empty transcription text not allowed.")
                else:
                    asyncio.create_task(self._small_model.process_message(message))
                    response = None  # Response will be handled asynchronously
            
            elif message.type == 'stt.heartbeat':
                # Handle heartbeat keep-alive messages from STT service
                logger.debug(f"MessageRouter: Received heartbeat from STT client {message.client_id}")
                # Simply acknowledge the heartbeat - no further processing needed
                response = self._create_ack_message(message, "Heartbeat acknowledged.")

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

            elif message.type == 'manual.request':
                # Allow users to manually request an explanation for a term
                try:
                    term = (message.payload.get('term') or '').strip()
                    context = (message.payload.get('context') or term).strip()
                    domain = (message.payload.get('domain') or '').strip()
                    explanation_style = (message.payload.get('explanation_style') or 'detailed').strip()
                    if not term:
                        response = self._create_error_message(message, ErrorTypes.INVALID_INPUT, "Missing 'term' in manual.request payload.")
                    else:
                        # Generate confidence score for manual request using AI detection
                        ai_detected_terms = await self._small_model.detect_terms_with_ai(
                            context,
                            message.payload.get("user_role")
                        )
                        
                        # Find confidence for the requested term, or use a default confidence for manual requests
                        confidence = 0.7  # Default confidence for manual requests
                        for ai_term in ai_detected_terms:
                            if ai_term.get("term", "").lower() == term.lower():
                                confidence = ai_term.get("confidence", 0.7)
                                break
                        
                        detected_terms = [{
                            "term": term,
                            "timestamp": int(time.time()),
                            "context": context,
                            "domain": domain,  # Include domain for AI processing
                            "confidence": confidence,
                            "explanation_style": explanation_style,  # Include explanation style
                        }]
                        success = await self._small_model.write_detection_to_queue(message, detected_terms)
                        if success:
                            response = self._create_ack_message(message, f"manual.request accepted for term '{term}'")
                        else:
                            response = self._create_error_message(message, ErrorTypes.PROCESSING_ERROR, "Failed to enqueue manual detection.")
                except Exception as e:
                    logger.error(f"Error handling manual.request: {e}", exc_info=True)
                    response = self._create_error_message(message, ErrorTypes.INTERNAL_SERVER_ERROR, "Unhandled error during manual.request.")

            elif message.type == 'explanation.retry':
                # Allow users to request a regenerated explanation for a term
                try:
                    term = (message.payload.get('term') or '').strip()
                    context = (message.payload.get('context') or term).strip()
                    original_explanation_id = message.payload.get('original_explanation_id')
                    explanation_style = message.payload.get('explanation_style', 'detailed')
                    
                    if not term:
                        response = self._create_error_message(message, ErrorTypes.INVALID_INPUT, "Missing 'term' in explanation.retry payload.")
                    else:
                        detected_terms = [{
                            "term": term,
                            "timestamp": int(time.time()),
                            "context": context,
                            "explanation_style": explanation_style,
                            "original_explanation_id": original_explanation_id,
                            "is_retry": True
                        }]
                        success = await self._small_model.write_detection_to_queue(message, detected_terms)
                        if success:
                            response = self._create_ack_message(message, f"explanation.retry accepted for term '{term}'")
                        else:
                            response = self._create_error_message(message, ErrorTypes.PROCESSING_ERROR, "Failed to enqueue retry detection.")
                except Exception as e:
                    logger.error(f"Error handling explanation.retry: {e}", exc_info=True)
                    response = self._create_error_message(message, ErrorTypes.INTERNAL_SERVER_ERROR, "Unhandled error during explanation.retry.")

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