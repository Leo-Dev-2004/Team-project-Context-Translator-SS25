# Backend/AI/SmallModel.py (CORRECTED)

import logging
from typing import Dict, Any
from uuid import uuid4
import time

# --- FIX: REMOVE THE CLASS DEFINITION OF UniversalMessage FROM HERE ---
# --- INSTEAD, IMPORT IT FROM THE CENTRAL MODELS FILE ---
from Backend.models.UniversalMessage import UniversalMessage, ErrorTypes # Import ErrorTypes if you plan to use it for error messages from SmallModel

logger = logging.getLogger(__name__)

class SmallModel:
    """
    A dummy AI model to process incoming STT transcriptions.
    """
    def __init__(self):
        logger.info("SmallModel initialized.")

    async def DummyProcessIncoming(self, message: UniversalMessage, output_queue):
        """
        Retrieves transcribed text, puts it in parenthesis, outputs to system.log,
        and passes it back to the BackendServiceDispatcher for the frontend.
        """
        if message.type == "stt.transcription":
            try:
                transcribed_text = message.payload.get("text", "")
                language = message.payload.get("language", "unknown")
                confidence = message.payload.get("confidence", 0.0)

                processed_text = f"({transcribed_text})"

                # Log to system.log (this will be picked up by SystemRunner's stderr capture)
                logger.info(f"SmallModel processed transcription: '{processed_text}' (Lang: {language}, Conf: {confidence})")

                # Create a new message to send to the frontend
                # You might choose a different type, e.g., "ai.processed_transcription"
                # For simplicity, let's assume it's directly for TTS or display
                response_message = UniversalMessage(
                    id=str(uuid4()),
                    type="tts.speak", # Or "display.text" or "ai.processed_text"
                    timestamp=time.time(),
                    payload={"text": processed_text, "original_transcription_id": message.id},
                    origin="small_model",
                    client_id=message.client_id, # Keep the client_id to route back to the correct frontend client
                    destination="frontend"
                )

                # Put the new message into the output queue for the dispatcher to send
                await output_queue.put(response_message)
                logger.debug(f"SmallModel enqueued processed message for frontend: {response_message.id}")

            except KeyError as e:
                logger.error(f"SmallModel: Missing key in transcription payload: {e}")
                # You can add error message sending here, using the imported ErrorTypes
                # error_msg = UniversalMessage(
                #     id=str(uuid4()), type=ErrorTypes.PROCESSING_ERROR.value, timestamp=time.time(),
                #     payload={"error": f"Missing data in STT transcription: {e}", "original_message_id": message.id},
                #     origin="small_model", client_id=message.client_id, destination="frontend"
                # )
                # await output_queue.put(error_msg)
            except Exception as e:
                logger.error(f"SmallModel: An unexpected error occurred during processing: {e}", exc_info=True)
                # You can add error message sending here, using the imported ErrorTypes
                # error_msg = UniversalMessage(
                #     id=str(uuid4()), type=ErrorTypes.INTERNAL_SERVER_ERROR.value, timestamp=time.time(),
                #     payload={"error": f"SmallModel processing failed: {e}", "original_message_id": message.id},
                #     origin="small_model", client_id=message.client_id, destination="frontend"
                # )
                # await output_queue.put(error_msg)
        else:
            logger.warning(f"SmallModel: Received unexpected message type: {message.type}. Not processing.")

# For direct testing (optional)
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    test_model = SmallModel()
    from asyncio import Queue, run

    async def test_dummy_process():
        mock_output_queue = Queue()
        mock_message = UniversalMessage( # This UniversalMessage is now the one imported from Backend.models.UniversalMessage
            id="test-transcription-123",
            type="stt.transcription",
            timestamp=time.time(),
            payload={"text": "hello world", "language": "en", "confidence": 0.95},
            origin="stt_module",
            client_id="test_client_id",
            destination="frontend" # Explicitly set the destination
        )
        await test_model.DummyProcessIncoming(mock_message, mock_output_queue)
        if not mock_output_queue.empty():
            response = await mock_output_queue.get()
            print(f"\nTest Output Queue received: {response.to_dict()}")
        else:
            print("\nTest Output Queue is empty.")

    run(test_dummy_process())