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
        and returns a response message.
        This method is called directly by other components (e.g., MessageRouter).
        """
        if message.type == "stt.transcription":
            try:
                transcribed_text = message.payload.get("text", "")
                language = message.payload.get("language", "unknown")
                confidence = message.payload.get("confidence", 0.0)

                # Add a check for empty transcription text
                if not transcribed_text:
                    logger.warning(f"SmallModel: Received empty transcription for message ID: {message.id}. Returning processing error message.")
                    # Create an error message directly
                    error_msg = UniversalMessage(
                        id=message.id, # Use original ID for traceability
                        type=ErrorTypes.PROCESSING_ERROR.value,
                        timestamp=time.time(),
                        payload={"error": "SmallModel received empty transcription text.", "original_message_id": message.id},
                        origin="small_model",
                        client_id=message.client_id,
                        destination="frontend", # Error goes back to frontend
                        processing_path=message.processing_path + [ # Append to existing path
                            ProcessingPathEntry(
                                processor="SmallModel",
                                status="validation_failed_empty_text",
                                timestamp=time.time(),
                                completed_at=time.time(),
                                details={"reason": "Empty transcription text received"}
                            )
                        ]
                    )
                    return error_msg # RETURN the error message

                processed_text = f"({transcribed_text})"

                # Add a processing path entry for SmallModel's action
                message.processing_path.append(
                    ProcessingPathEntry(
                        processor="SmallModel",
                        status="transcription_processed",
                        timestamp=time.time(),
                        details={
                            "action": "Text put in parenthesis",
                            "input_text_snippet": transcribed_text[:50] + "..." if len(transcribed_text) > 50 else transcribed_text,
                            "output_text_snippet": processed_text[:50] + "..." if len(processed_text) > 50 else processed_text,
                            "language": language,
                            "confidence": confidence
                        },
                        completed_at=time.time() # This step is now completed
                    )
                )

                logger.info(f"SmallModel processed transcription: '{processed_text}' (Lang: {language}, Conf: {confidence})")

                # Create a new message to send back as the response
                response_message = UniversalMessage(
                    id=message.id, # Keep the original ID
                    type="tts.speak", # Or "display.text" or "ai.processed_text"
                    timestamp=time.time(), # Use current time for this step's timestamp
                    payload={"text": processed_text, "original_transcription_id": message.id}, # Keep original ID for reference
                    origin="small_model",
                    client_id=message.client_id,
                    destination="frontend", # Assuming it goes directly to frontend for TTS/display
                    processing_path=message.processing_path # Pass the updated path
                )
                return response_message # RETURN the processed message

            except KeyError as e:
                logger.error(f"SmallModel: Missing key in transcription payload: {e}")
                # Create and RETURN an error message
                error_msg = UniversalMessage(
                    id=message.id, # Use original ID for traceability
                    type=ErrorTypes.PROCESSING_ERROR.value,
                    timestamp=time.time(),
                    payload={"error": f"SmallModel: Missing data in STT transcription: {e}", "original_message_id": message.id},
                    origin="small_model",
                    client_id=message.client_id,
                    destination="frontend",
                    processing_path=message.processing_path + [
                        ProcessingPathEntry(
                            processor="SmallModel",
                            status="error_missing_payload_key",
                            timestamp=time.time(),
                            completed_at=time.time(),
                            details={"error_message": str(e)}
                        )
                    ]
                )
                return error_msg # RETURN the error message
            except Exception as e:
                logger.error(f"SmallModel: An unexpected error occurred during processing: {e}", exc_info=True)
                # Create and RETURN an error message
                error_msg = UniversalMessage(
                    id=message.id, # Use original ID for traceability
                    type=ErrorTypes.INTERNAL_SERVER_ERROR.value,
                    timestamp=time.time(),
                    payload={"error": f"SmallModel processing failed: {e}", "original_message_id": message.id},
                    origin="small_model",
                    client_id=message.client_id,
                    destination="frontend",
                    processing_path=message.processing_path + [
                        ProcessingPathEntry(
                            processor="SmallModel",
                            status="error_unexpected_exception",
                            timestamp=time.time(),
                            completed_at=time.time(),
                            details={"error_message": str(e)}
                        )
                    ]
                )
                return error_msg # RETURN the error message
        else:
            logger.warning(f"SmallModel: Received unexpected message type: {message.type}. Not processing.")
            # If SmallModel isn't meant to handle this type, it should return the original message
            # with an added processing path entry indicating it was not handled.
            message.processing_path.append(
                ProcessingPathEntry(
                    processor="SmallModel",
                    status="skipped_unhandled_type",
                    timestamp=time.time(),
                    completed_at=time.time(),
                    details={"reason": f"Message type {message.type} not handled by SmallModel"}
                )
            )
            return message # RETURN the original message, marked as skipped

# No 'run()' method in this version.
# No 'if __name__ == "__main__":' block that runs queues or a loop.
# Testing would involve instantiating SmallModel and calling process_message directly.