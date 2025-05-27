import asyncio
import logging
import time
import uuid
from typing import Optional, Dict, List, Any
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
        """Nachrichtenverarbeitungslogik mit vollständiger Pfadverfolgung"""
        try:
            if not isinstance(message, dict):
                raise ValueError("Invalid message format")

            # Ensure required fields exist
            message.setdefault('id', str(uuid.uuid4()))
            message.setdefault('client_id', 'unknown')
            message.setdefault('processing_path', [])
            message.setdefault('forwarding_path', [])

            # Ensure processing_path exists and is a list
            if 'processing_path' not in message or not isinstance(message['processing_path'], list):
                message['processing_path'] = []
            
            # Add current processing step
            message['processing_path'].append('message_processor')

            # Add processing metadata
            message['status'] = 'processed'
            message['processed_at'] = time.time()

            # Update processing path with completion
            message['processing_path'][-1]['status'] = 'completed'
            message['processing_path'][-1]['completed_at'] = time.time()

            # Create comprehensive frontend notification
            frontend_msg = {
                'type': 'status_update',
                'data': {
                    'original_id': message.get('id'),
                    'original_type': message.get('type'),
                    'status': 'processed',
                    'processing_path': message.get('processing_path', []),
                    'forwarding_path': message.get('forwarding_path', []),
                    'timestamp': time.time()
                },
                'id': str(uuid.uuid4()),
                'client_id': message.get('client_id'),
                'processing_path': [],
                'forwarding_path': []
            }

            # Forward both the processed message and notification
            await self._safe_enqueue(self._frontend_queue, frontend_msg)
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
