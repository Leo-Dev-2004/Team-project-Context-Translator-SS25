import logging
import asyncio
from typing import Optional
from ..models.UniversalMessage import UniversalMessage, ErrorTypes

logger = logging.getLogger(__name__)

class SmallModel:
    """
    Processes transcriptions, detects domain-specific terms, and forwards
    explanation tasks to the MainModel via a shared queue.
    """
    def __init__(self, main_model_queue: asyncio.Queue):
        """
        Initializes the SmallModel.

        Args:
            main_model_queue: The asyncio queue to send tasks to the MainModel.
        """
        self.main_model_queue = main_model_queue
        # --- Dummy list of domain-specific words to detect ---
        self.domain_words = {"photosynthesis", "mitochondria", "osmosis", "taxonomy"}
        logger.info(f"SmallModel initialized (as a term detector for: {self.domain_words}).")

    async def process_message(self, message: UniversalMessage) -> None:
        """
        Processes a 'stt.transcription' message.
        - Detects domain-specific words.
        - Puts tasks in the MainModel's queue for each detected word.
        - Does NOT return a message directly to the client.
        """
        if message.type != "stt.transcription":
            logger.warning(f"SmallModel received unexpected message type: {message.type}. Not processing.")
            return

        try:
            transcribed_text = message.payload.get("text", "")
            if not transcribed_text:
                raise ValueError("Received empty transcription text.")

            logger.info(f"SmallModel processing text for client {message.client_id}: '{transcribed_text}'")

            # --- Word Detection Logic ---
            # Create a clean set of words from the text to check against our domain list
            words_in_text = {word.strip(".,!?").lower() for word in transcribed_text.split()}
            
            # Find the intersection between words in the text and our domain list
            found_terms = words_in_text.intersection(self.domain_words)

            if not found_terms:
                logger.info("No domain-specific terms found.")
                return

            # --- Enqueue tasks for the MainModel ---
            for term in found_terms:
                task = {
                    "term": term,
                    "context": transcribed_text,
                    "client_id": message.client_id
                }
                await self.main_model_queue.put(task)
                logger.info(f"Enqueued explanation task for term '{term}' for client {message.client_id}")

            # No response is returned. The function's work is done.

        except Exception as e:
            logger.error(f"SmallModel failed to process message {message.id}: {e}", exc_info=True)
            # In a real app, you might want to enqueue a special error message
            # for the WebSocket manager to send, but for now, we just log it.