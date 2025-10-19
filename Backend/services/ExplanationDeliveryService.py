import asyncio
import json
import logging
import time
import os
from pathlib import Path
from typing import Dict, List, Optional, Set

import aiofiles

from ..models.UniversalMessage import UniversalMessage
from ..queues.QueueTypes import AbstractMessageQueue

logger = logging.getLogger(__name__)

class ExplanationDeliveryService:
    """
    Monitors explanations_queue.json and delivers explanations to frontend clients.
    
    This service is a CONSUMER that polls a file queue and pushes messages to the
    outgoing WebSocket queue. It is fully asynchronous and thread-safe.
    """
    
    def __init__(self, outgoing_queue: AbstractMessageQueue):
        self.outgoing_queue = outgoing_queue
        self.explanations_file = Path("Backend/AI/explanations_queue.json")
        
        # A lock is essential to prevent race conditions when updating the shared queue file.
        self.queue_lock = asyncio.Lock()
        
        # In-memory set to track delivered IDs for the current session to prevent duplicates.
        self.delivered_explanations: Set[str] = set()
        
        # Event-driven notification system to replace polling
        self._new_explanation_event = asyncio.Event()
        
        self._running = False
        self._task: Optional[asyncio.Task] = None
        logger.info("ExplanationDeliveryService initialized")

    async def start(self):
        """Start the explanation monitoring service."""
        if not self._running:
            self._running = True
            self._task = asyncio.create_task(self._monitor_explanations())
            logger.info("ExplanationDeliveryService started monitoring explanations queue")

    def trigger_immediate_check(self):
        """Trigger immediate check for new explanations without waiting for polling interval."""
        if self._running:
            self._new_explanation_event.set()
            logger.debug("Triggered immediate explanation check")

    async def stop(self):
        """Stop the explanation monitoring service."""
        if self._running:
            self._running = False
            if self._task:
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass
            logger.info("ExplanationDeliveryService stopped")

    async def _monitor_explanations(self):
        logger.info("Started monitoring explanations queue for ready explanations")
        while self._running:
            try:
                # Continuously process until the queue is empty
                while True:
                    ready_explanations = await self._load_ready_explanations()
                    if not ready_explanations:
                        break # Break the inner loop if queue is empty

                    # Process the entire batch that was found
                    await self._process_and_deliver_batch(ready_explanations)

                # If the queue was empty, wait for event notification or timeout
                # This replaces the fixed 1-second polling delay with event-driven approach
                try:
                    await asyncio.wait_for(self._new_explanation_event.wait(), timeout=5.0)
                    # Clear the event flag for next iteration
                    self._new_explanation_event.clear()
                except asyncio.TimeoutError:
                    # Timeout is normal - provides periodic check as fallback
                    pass

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in explanation monitoring loop: {e}", exc_info=True)
                await asyncio.sleep(1)

    async def _process_and_deliver_batch(self, batch: List[Dict]):
        """Processes a given batch of explanations."""
        delivered_ids_in_batch = []
        for explanation in batch:
            explanation_id = explanation.get("id")
            if explanation_id and explanation_id not in self.delivered_explanations:
                await self._deliver_explanation(explanation)
                self.delivered_explanations.add(explanation_id)
                delivered_ids_in_batch.append(explanation_id)
        
        if delivered_ids_in_batch:
            await self._mark_batch_as_delivered(delivered_ids_in_batch)


    async def _process_and_deliver(self):
        """Load, deliver, and update status for ready explanations."""
        ready_explanations = await self._load_ready_explanations()
        
        if not ready_explanations:
            return

        for explanation in ready_explanations:
            explanation_id = explanation.get("id")
            if explanation_id and explanation_id not in self.delivered_explanations:
                await self._deliver_explanation(explanation)
                self.delivered_explanations.add(explanation_id)
        
        # Mark all newly delivered items as "delivered" in a single file write.
        await self._mark_batch_as_delivered( [exp.get("id") for exp in ready_explanations] ) # type: ignore

    async def _load_ready_explanations(self) -> List[Dict]:
        """Asynchronously load explanations with status 'ready_for_delivery'."""
        async with self.queue_lock:
            try:
                async with aiofiles.open(self.explanations_file, 'r', encoding='utf-8') as f:
                    content = await f.read()
                
                explanations = json.loads(content) if content.strip() else []
                
                ready = [
                    exp for exp in explanations 
                    if exp.get("status") == "ready_for_delivery"
                ]
                
                if ready:
                    logger.debug(f"Found {len(ready)} ready explanations to deliver")
                
                return ready
            except FileNotFoundError:
                return []
            except Exception as e:
                logger.error(f"Error loading explanations queue: {e}")
                return []

    async def _deliver_explanation(self, explanation: Dict):
        """Format and enqueue a single explanation for delivery."""
        try:
            # Use the message_type from the explanation, defaulting to "explanation.new"
            message_type = explanation.get("message_type", "explanation.new")
            
            message = UniversalMessage(
                id=f"explanation_delivery_{explanation.get('id', 'unknown')}",
                type=message_type,
                timestamp=time.time(),
                payload={
                    "explanation": {
                        "id": explanation.get("id"),
                        "term": explanation.get("term"),
                        "content": explanation.get("explanation"),
                        "context": explanation.get("context"),
                        "timestamp": explanation.get("timestamp"),
                        "client_id": explanation.get("client_id"),
                        "user_session_id": explanation.get("user_session_id"),
                        "confidence": explanation.get("confidence", 0),
                        "original_explanation_id": explanation.get("original_explanation_id")
                    }
                },
                destination="all_frontends", # Simplified to always broadcast
                origin="explanation_delivery_service",
                client_id=explanation.get("client_id")
            )
            
            await self.outgoing_queue.enqueue(message)
            logger.info(f"Delivered {'retry ' if message_type == 'explanation.retry' else ''}explanation for term '{explanation.get('term')}' (id: {explanation.get('id')})")
        except Exception as e:
            logger.error(f"Error delivering explanation {explanation.get('id')}: {e}", exc_info=True)

    async def _mark_batch_as_delivered(self, delivered_ids: List[str]):
        """Safely mark a batch of explanations as delivered in the queue file."""
        if not delivered_ids:
            return

        delivered_id_set = set(delivered_ids)
        async with self.queue_lock:
            try:
                async with aiofiles.open(self.explanations_file, 'r', encoding='utf-8') as f:
                    content = await f.read()
                
                explanations = json.loads(content) if content.strip() else []

                for explanation in explanations:
                    if explanation.get("id") in delivered_id_set:
                        explanation["status"] = "delivered"
                        explanation["delivered_at"] = time.time()
                
                temp_file = self.explanations_file.with_suffix('.tmp')
                async with aiofiles.open(temp_file, 'w', encoding='utf-8') as f:
                    await f.write(json.dumps(explanations, indent=2, ensure_ascii=False))
                
                await asyncio.to_thread(os.replace, str(temp_file), str(self.explanations_file))
                
                logger.debug(f"Marked {len(delivered_ids)} explanations as delivered in queue file.")
            except FileNotFoundError:
                logger.error("Cannot mark explanations as delivered: queue file not found.")
            except Exception as e:
                logger.error(f"Error marking explanations as delivered: {e}")