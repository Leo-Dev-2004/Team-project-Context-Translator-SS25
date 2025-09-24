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
1
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