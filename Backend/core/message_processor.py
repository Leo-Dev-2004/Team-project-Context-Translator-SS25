import asyncio
import logging
import time
from typing import Optional, Dict
from ..queues.shared_queue import (
    get_to_backend_queue,
    get_from_backend_queue,
    get_to_frontend_queue
)

logger = logging.getLogger(__name__)

class MessageProcessor:
    def __init__(self):
        self._running = False
        self._input_queue = None
        self._output_queue = None
        self._fronRtend_queue = None

    async def initialize(self):
        """Sichere Initialisierung mit Queue-Validierung"""
        try:
            self._input_queue = get_to_backend_queue()
            self._output_queue = get_from_backend_queue()
            self._frontend_queue = get_to_frontend_queue()

            if None in (self._input_queue, self._output_queue, self._frontend_queue):
                raise RuntimeError("One or more queues not initialized")

            logger.info("MessageProcessor queues verified")
        except Exception as e:
            logger.error(f"Failed to initialize MessageProcessor: {str(e)}")
            raise

    async def process(self):
        """Main processing loop with robust error handling"""
        self._running = True
        logger.info("Starting MessageProcessor")
        
        processed_count = 0
        last_log_time = time.time()
        
        while self._running:
            try:
                # Get message with timeout
                message = await self._safe_dequeue(self._input_queue)
                if message is None:
                    await asyncio.sleep(0.1)
                    continue

                # Process message
                start_time = time.time()
                processed_msg = await self._process_message(message)
                processing_time = time.time() - start_time

                if processed_msg:
                    # Forward to backend queue
                    await self._safe_enqueue(self._output_queue, processed_msg)
                    
                    # Create status update for frontend
                    status_update = {
                        'type': 'status_update',
                        'data': {
                            'id': processed_msg.get('id'),
                            'status': 'processed',
                            'processing_time': processing_time,
                            'original_type': processed_msg.get('type')
                        },
                        'timestamp': time.time()
                    }
                    await self._safe_enqueue(self._frontend_queue, status_update)

                processed_count += 1
                
                # Periodic logging
                if time.time() - last_log_time > 5:
                    logger.info(f"Processed {processed_count} messages")
                    last_log_time = time.time()
                    processed_count = 0

            except Exception as e:
                logger.error(f"Error during message processing: {str(e)}")
                await asyncio.sleep(1)  # Backoff on errors

        logger.info("MessageProcessor stopped")

    async def _safe_dequeue(self, queue) -> Optional[Dict]:
        """Thread-sicheres Dequeue mit Error-Handling"""
        try:
            return await queue.dequeue() if queue else None
        except Exception as e:
            logger.warning(f"Dequeue failed: {str(e)}")
            return None

    async def _safe_enqueue(self, queue, message) -> bool:
        """Thread-sicheres Enqueue mit Error-Handling"""
        try:
            if queue:
                await queue.enqueue(message)
                return True
            return False
        except Exception as e:
            logger.warning(f"Enqueue failed: {str(e)}")
            return False

    async def _process_message(self, message: Dict) -> Optional[Dict]:
        """Nachrichtenverarbeitungslogik"""
        try:
            # Ihre Verarbeitungslogik hier
            if not isinstance(message, dict):
                raise ValueError("Invalid message format")
                
            message['status'] = 'processed'
            message['processed_at'] = time.time()
            return message
        except Exception as e:
            logger.error(f"Message processing failed: {str(e)}")
            return None

    async def stop(self):
        """Geordnetes Herunterfahren"""
        self._running = False
        logger.debug("MessageProcessor shutdown initiated")

    def get_input_queue_size(self):
        """Return the size of the input queue."""
        try:
            return self._input_queue.size() if self._input_queue else 0
        except Exception as e:
            logger.warning(f"Failed to get input queue size: {str(e)}")
            return 0
