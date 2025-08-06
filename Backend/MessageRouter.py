# Backend/MessageRouter.py (Final Version with Intelligent Routing)

import asyncio
import logging
import time
import uuid
from typing import Optional

from pydantic import ValidationError

from .models.UniversalMessage import UniversalMessage, ProcessingPathEntry, ErrorTypes
from .core.Queues import queues
from .queues.QueueTypes import AbstractMessageQueue
from .AI.SmallModel import SmallModel
from .dependencies import get_simulation_manager
from .dependencies import get_session_manager_instance


logger = logging.getLogger(__name__)

class MessageRouter:
    def __init__(self):
        self._session_manager = get_session_manager_instance()

        # Der Router lauscht auf ZWEI Queues: eine für externe und eine für interne Nachrichten
        self._client_incoming_queue: AbstractMessageQueue = queues.incoming
        self._service_outgoing_queue: AbstractMessageQueue = queues.outgoing
        
        # Der Router sendet NUR an die WebSocket-Queue. Andere Dienste lesen hier nicht.
        self._websocket_out_queue: AbstractMessageQueue = queues.websocket_out
        
        self._running = False
        self._router_task: Optional[asyncio.Task] = None
        self._small_model: SmallModel = SmallModel()
        self._simulation_manager = get_simulation_manager()

        logger.info("MessageRouter initialized with dependencies (SmallModel, SimulationManager).")

    async def start(self):
        if not self._running:
            self._running = True
            # NEU: Startet eine Haupt-Task, die beide Listener-Tasks verwaltet
            self._router_task = asyncio.create_task(self._run_message_loops())
            logger.info("MessageRouter started with dual listeners.")

    async def stop(self):
        if self._running:
            self._running = False
            if self._router_task:
                self._router_task.cancel()
                try:
                    await self._router_task
                except asyncio.CancelledError:
                    logger.info("MessageRouter tasks cancelled successfully.")

    async def _run_message_loops(self):
        """Orchestriert die beiden parallelen Listener-Tasks."""
        client_listener_task = asyncio.create_task(self._client_message_listener())
        service_listener_task = asyncio.create_task(self._service_message_listener())
        
        await asyncio.gather(client_listener_task, service_listener_task)

    async def _client_message_listener(self):
        """Bearbeitet Nachrichten, die direkt von Clients (WebSocket) kommen."""
        logger.info("MessageRouter: Listening for messages from clients...")
        while self._running:
            try:
                message = await self._client_incoming_queue.dequeue()
                logger.debug(f"Router received client message '{message.type}' from {message.client_id}.")
                await self._process_client_message(message)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in client message listener: {e}", exc_info=True)
                await asyncio.sleep(1)

    async def _service_message_listener(self):
        """Bearbeitet Nachrichten, die von internen Diensten (z.B. SimulationManager) kommen."""
        logger.info("MessageRouter: Listening for messages from backend services...")
        while self._running:
            try:
                message = await self._service_outgoing_queue.dequeue()
                logger.debug(f"Router received service message '{message.type}' from {message.origin}.")
                await self._route_service_message(message)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in service message listener: {e}", exc_info=True)
                await asyncio.sleep(1)

    async def _process_client_message(self, message: UniversalMessage):
        """Verarbeitet eine einzelne Nachricht von einem Client."""
        response: Optional[UniversalMessage] = None
        try:
            if message.type == 'stt.transcription':
                response = await self._small_model.process_message(message)
            elif message.type == 'simulation.start' and self._simulation_manager:
                if message.client_id is not None:
                    await self._simulation_manager.start(client_id=message.client_id)
                    response = self._create_ack_message(message, "Simulation start command received.")
                else:
                    response = self._create_error_message(message, ErrorTypes.INVALID_MESSAGE_FORMAT, "Missing client_id for simulation.start.")
            elif message.type == 'simulation.stop' and self._simulation_manager:
                await self._simulation_manager.stop(client_id=message.client_id)
                response = self._create_ack_message(message, "Simulation stop command received.")
            elif message.type == 'ping':
                response = self._create_pong_message(message)
            elif message.type == 'stt.init':
                logger.info(f"STT module connected: {message.client_id}. No action needed.")
            elif message.type == 'session.start':
                if self._session_manager and message.client_id is not None:
                    code = self._session_manager.create_session(creator_client_id=message.client_id)
                    if code:
                        response = UniversalMessage(
                            type='session.created',
                            payload={'code': code},
                            destination=message.client_id,
                            origin='MessageRouter',
                            client_id=message.client_id
                        )
                    else:
                        response = self._create_error_message(message, ErrorTypes.INVALID_INPUT, "Eine Session ist bereits aktiv.")
                else:
                    response = self._create_error_message(message, ErrorTypes.INTERNAL_SERVER_ERROR, "SessionManager nicht verfügbar.")

            elif message.type == 'session.join':
                code_to_join = message.payload.get('code')
                if self._session_manager and code_to_join and message.client_id is not None:
                    success = self._session_manager.join_session(joiner_client_id=message.client_id, code=code_to_join)
                    if success:
                        response = UniversalMessage(
                            type='session.joined',
                            payload={'code': code_to_join, 'message': 'Erfolgreich beigetreten!'},
                            destination=message.client_id,
                            origin='MessageRouter',
                            client_id=message.client_id
                        )
                    else:
                        response = self._create_error_message(message, ErrorTypes.INVALID_INPUT, "Session-Code ist ungültig oder die Session existiert nicht.")
                else:
                    response = self._create_error_message(message, ErrorTypes.INVALID_INPUT, "SessionManager nicht verfügbar oder kein Code angegeben.")
            else:
                response = self._create_error_message(message, ErrorTypes.UNKNOWN_MESSAGE_TYPE, f"Unknown message type: '{message.type}'")
           

            
            if response:
                await self._websocket_out_queue.enqueue(response)

        except Exception as e:
            logger.error(f"Error processing client message {message.id}: {e}", exc_info=True)
            error_response = self._create_error_message(message, ErrorTypes.INTERNAL_SERVER_ERROR, str(e))
            await self._websocket_out_queue.enqueue(error_response)

    async def _route_service_message(self, message: UniversalMessage):
        """Routet eine Nachricht von einem internen Service an die entsprechenden Clients."""
        try:
            # Hier findet das "intelligente" Routing statt.
            # Wenn ein Service an "frontend" senden will, übersetzen wir das
            # in eine Nachricht für die Gruppe "all_frontends".
            if message.destination == "frontend":
                message.destination = "all_frontends"
                await self._websocket_out_queue.enqueue(message)
                logger.debug(f"Routed service message '{message.type}' to group '{message.destination}'.")
            else:
                # Hier könnte Logik für Service-zu-Service-Kommunikation stehen
                logger.warning(f"Unhandled service message destination: '{message.destination}'")
        except Exception as e:
            logger.error(f"Error routing service message {message.id}: {e}", exc_info=True)

    # --- Hilfsfunktionen für konsistente Antworten ---
    def _create_ack_message(self, origin_msg: UniversalMessage, text: str) -> UniversalMessage:
        return UniversalMessage(
            type='system.acknowledgement',
            payload={'message': text, 'original_message_id': origin_msg.id},
            destination=origin_msg.client_id, # Direkt an den Absender zurück
            origin='MessageRouter',
            client_id=origin_msg.client_id
        )

    def _create_error_message(self, origin_msg: UniversalMessage, err_type: ErrorTypes, text: str) -> UniversalMessage:
        return UniversalMessage(
            type=err_type.value,
            payload={'error': text, 'original_message_id': origin_msg.id},
            destination=origin_msg.client_id, # Direkt an den Absender zurück
            origin='MessageRouter',
            client_id=origin_msg.client_id
        )

    def _create_pong_message(self, origin_msg: UniversalMessage) -> UniversalMessage:
        return UniversalMessage(
            type='pong',
            payload={'timestamp': time.time()},
            destination=origin_msg.client_id, # Direkt an den Absender zurück
            origin='MessageRouter',
            client_id=origin_msg.client_id
        )