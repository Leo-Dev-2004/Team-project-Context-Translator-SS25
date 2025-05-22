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
        """Hauptverarbeitungsschleife mit robustem Error-Handling"""
        self._running = True
        logger.info("Starting MessageProcessor")
        
        # Message statistics
        processed_count = 0
        last_log_time = time.time()
        
        while self._running:
            try:
                # Get message with timeout
                message = await self._safe_dequeue(self._input_queue)
                if message is None:
                    await asyncio.sleep(0.1)
                    continue
                    
                # Log message receipt
                logger.debug(f"Processing message {message['id']} from {message.get('_trace', {}).get('source')}")
                
                # Process message
                start_time = time.time()
                processed_msg = await self._process_message(message)
                processing_time = time.time() - start_time
        
        # Setup structured logging
        msg_counter = 0
        last_log_time = time.time()

        while self._running:
            try:
                # Sicherer Dequeue mit Timeout
                message = await self._safe_dequeue(self._input_queue)
                if message is None:
                    await asyncio.sleep(0.1)
                    continue

                # Nachrichtenverarbeitung
                processed_msg = await self._process_message(message)
                if processed_msg:
                    # Weiterleitung an Backend und Frontend
                    await self._safe_enqueue(self._output_queue, processed_msg)
                    await self._safe_enqueue(self._frontend_queue, {
                        'type': 'status_update',
                        'data': processed_msg,
                        'timestamp': time.time()
                    })

            except Exception as e:
                logger.error(f"Processing error: {str(e)}")
                await asyncio.sleep(1)  # Backoff bei Fehlern

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
