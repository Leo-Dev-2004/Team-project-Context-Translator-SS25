# Backend/AI/SmallModel.py

import logging
import time
from typing import Dict, Any, Optional
from uuid import uuid4

from ..models.UniversalMessage import UniversalMessage, ErrorTypes, ProcessingPathEntry

logger = logging.getLogger(__name__)

class SmallModel:
    """
    A dummy AI model that processes a UniversalMessage via a direct function call
    and returns a UniversalMessage. It does NOT manage its own queues or run loop.
    """
    def __init__(self):
        logger.info("SmallModel initialized (as a direct message processor).")

    async def process_message(self, message: UniversalMessage) -> UniversalMessage:
        """
        Processes an incoming UniversalMessage (specifically 'stt.transcription' types)
        and returns a response message correctly addressed to the original sender.
        """
        if message.type != "stt.transcription":
            logger.warning(f"SmallModel received unexpected message type: {message.type}. Not processing.")
            # Create an error message to send back
            return UniversalMessage(
                type=ErrorTypes.INVALID_ACTION.value,
                payload={"error": f"SmallModel cannot process message type '{message.type}'"},
                origin="SmallModel",
                destination=message.client_id,  # Send error back to the original client
                client_id=message.client_id
            )

        try:
            transcribed_text = message.payload.get("text", "")
            if not transcribed_text:
                raise ValueError("Received empty transcription text.")

            # --- Dummy Processing Logic ---
            processed_text = f"Processed: '{transcribed_text}'"
            logger.info(f"SmallModel processed transcription for client {message.client_id}")
            # -----------------------------

            # Create a new message to send back as the response
            response_message = UniversalMessage(
                type="ai.processed_text",
                payload={"text": processed_text, "original_message_id": message.id},
                origin="small_model",
                # KORREKTUR: The destination is the client_id of the original message.
                destination=message.client_id,
                client_id=message.client_id

            )
            return response_message

        except Exception as e:
            logger.error(f"SmallModel failed to process message {message.id}: {e}", exc_info=True)
            # Create and return a detailed error message
            return UniversalMessage(
                type=ErrorTypes.PROCESSING_ERROR.value,
                payload={"error": f"SmallModel processing failed: {str(e)}", "original_message_id": message.id},
                origin="small_model",
                destination=message.client_id, # Ensure error also goes to the correct client
                client_id=message.client_id
            )