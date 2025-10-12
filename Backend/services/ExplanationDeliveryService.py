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
    Monitors explanations_queue.json and delivers explanations directly to clients.

    This version uses an "atomic pop" from the file queue. It reads the entire
    queue, removes all ready items in one atomic operation, and then processes them.
    This is the safest way to prevent duplicate processing and ensure all items are handled.
    """
    
    def __init__(self, outgoing_queue: AbstractMessageQueue):
        self.outgoing_queue = outgoing_queue
        self.explanations_file = Path("Backend/AI/explanations_queue.json")
        self.queue_lock = asyncio.Lock()  # Lock to ensure atomic file operations
        self.delivered_explanations: Set[str] = set() # In-memory check for session duplicates
        self._new_explanation_event = asyncio.Event()
        self._running = False
        self._task: Optional[asyncio.Task] = None
        logger.info("ExplanationDeliveryService initialized (Atomic Pop Logic)")

    async def start(self):
        """Starts the explanation monitoring service."""
        if not self._running:
            self._running = True
            self._task = asyncio.create_task(self._monitor_explanations())
            logger.info("ExplanationDeliveryService started monitoring explanations queue")

    def trigger_immediate_check(self):
        """Triggers an immediate check for new explanations."""
        if self._running:
            self._new_explanation_event.set()

    async def stop(self):
        """Stops the explanation monitoring service."""
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
        """The main processing loop."""
        logger.info("Started monitoring explanations queue for ready explanations")
        while self._running:
            try:
                # Atomically pop all available items and process them.
                # The loop continues as long as items are being found.
                while await self._process_ready_batch():
                    pass  # An item was processed, so check again immediately

                # Once the queue is empty, wait for a new item notification or a timeout.
                try:
                    await asyncio.wait_for(self._new_explanation_event.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    pass  # Timeout is normal, acts as a periodic check
                finally:
                    self._new_explanation_event.clear()

            except asyncio.CancelledError:
                logger.info("Explanation monitoring was cancelled.")
                break
            except Exception as e:
                logger.error(f"Critical error in explanation monitoring loop: {e}", exc_info=True)
                await asyncio.sleep(5)

    async def _process_ready_batch(self) -> bool:
        """
        Atomically loads all ready explanations, removing them from the queue file,
        then processes the loaded batch. Returns True if items were processed, otherwise False.
        """
        items_to_process = await self._atomic_pop_ready_from_queue()

        if not items_to_process:
            return False # No work to do

        for explanation in items_to_process:
            explanation_id = explanation.get("id")

            if explanation_id and explanation_id in self.delivered_explanations:
                logger.warning(f"Skipping delivery of duplicate explanation ID (already sent this session): {explanation_id}")
                continue

            await self._deliver_explanation(explanation)
            
            if explanation_id:
                self.delivered_explanations.add(explanation_id)
        
        return True # Signal that work was done

    async def _atomic_pop_ready_from_queue(self) -> List[Dict]:
        """
        Safely reads the queue file, separates ready items from other items,
        and writes back only the other items. Returns the list of ready items.
        This is the core of the anti-duplication and continuous processing logic.
        """
        async with self.queue_lock:
            try:
                # 1. Read the entire queue file.
                async with aiofiles.open(self.explanations_file, 'r', encoding='utf-8') as f:
                    content = await f.read()
                
                all_explanations = json.loads(content) if content.strip() else []
                if not all_explanations:
                    return []

                # 2. Separate items into two lists.
                items_to_process = []
                items_to_keep_in_queue = []
                
                for exp in all_explanations:
                    # NOTE: We now treat the object as a UniversalMessage dictionary
                    if exp.get("payload", {}).get("explanation"):
                        items_to_process.append(exp)
                    else:
                        items_to_keep_in_queue.append(exp)

                if not items_to_process:
                    return []

                # 3. Atomically write back only the items that were not ready.
                temp_file = self.explanations_file.with_suffix('.tmp')
                async with aiofiles.open(temp_file, 'w', encoding='utf-8') as f:
                    await f.write(json.dumps(items_to_keep_in_queue, indent=2, ensure_ascii=False))
                await asyncio.to_thread(os.replace, str(temp_file), str(self.explanations_file))
                
                logger.debug(f"Atomically removed {len(items_to_process)} explanations from queue for processing.")
                
                # 4. Return the items that are now safe to process.
                return items_to_process

            except FileNotFoundError:
                return []
            except Exception as e:
                logger.error(f"Error during atomic pop from explanations queue: {e}")
                return []

    async def _deliver_explanation(self, message_dict: Dict):
        """Directly enqueues the UniversalMessage dictionary for WebSocket delivery."""
        try:
            # The dictionary is already a complete UniversalMessage, just enqueue it.
            await self.outgoing_queue.enqueue(UniversalMessage(**message_dict))
            
            term = message_dict.get("payload", {}).get("explanation", {}).get("term", "N/A")
            exp_id = message_dict.get("payload", {}).get("explanation", {}).get("id", "N/A")
            logger.info(f"Delivered explanation for '{term}' (ID: {exp_id})")

        except Exception as e:
            exp_id = message_dict.get("payload", {}).get("explanation", {}).get("id", "N/A")
            logger.error(f"Error enqueueing explanation {exp_id}: {e}", exc_info=True)