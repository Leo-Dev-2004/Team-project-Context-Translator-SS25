import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Dict, List, Optional, Set

from ..models.UniversalMessage import UniversalMessage
from ..queues.QueueTypes import AbstractMessageQueue

logger = logging.getLogger(__name__)

class ExplanationDeliveryService:
    """
    Service that monitors explanations_queue.json and delivers explanations to frontend clients via WebSocket.
    
    This service bridges the gap between MainModel explanation generation and frontend display by:
    1. Monitoring explanations_queue.json for status "ready_for_delivery"
    2. Converting explanations to UniversalMessage format
    3. Enqueueing messages to websocket_out queue for delivery
    4. Marking explanations as "delivered" to prevent duplicates
    """
    
    def __init__(self, outgoing_queue: AbstractMessageQueue):
        self.outgoing_queue = outgoing_queue
        self.explanations_file = Path("Backend/AI/explanations_queue.json")
        self.delivered_explanations: Set[str] = set()  # Track delivered explanation IDs
        self._running = False
        self._task: Optional[asyncio.Task] = None
        logger.info("ExplanationDeliveryService initialized")

    async def start(self):
        """Start the explanation monitoring service"""
        if not self._running:
            self._running = True
            self._task = asyncio.create_task(self._monitor_explanations())
            logger.info("ExplanationDeliveryService started monitoring explanations queue")

    async def stop(self):
        """Stop the explanation monitoring service"""
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
        """Monitor the explanations queue file and deliver ready explanations"""
        logger.info("Started monitoring explanations queue for ready explanations")
        
        while self._running:
            try:
                if self.explanations_file.exists():
                    ready_explanations = await self._load_ready_explanations()
                    
                    for explanation in ready_explanations:
                        explanation_id = explanation.get("id")
                        
                        # Skip if already delivered
                        if explanation_id and explanation_id not in self.delivered_explanations:
                            await self._deliver_explanation(explanation)
                            self.delivered_explanations.add(explanation_id)
                            
                            # Mark as delivered in the queue file
                            await self._mark_as_delivered(explanation_id)
                
                # Check every 2 seconds for new explanations
                await asyncio.sleep(0.5)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in explanation monitoring loop: {e}", exc_info=True)
                await asyncio.sleep(5)  # Wait longer on error

    async def _load_ready_explanations(self) -> List[Dict]:
        """Load explanations with status 'ready_for_delivery' from the queue file"""
        try:
            with open(self.explanations_file, 'r', encoding='utf-8') as f:
                explanations = json.load(f)
            
            # Filter for ready explanations that haven't been delivered
            ready_explanations = [
                exp for exp in explanations 
                if exp.get("status") == "ready_for_delivery"
                and exp.get("id") not in self.delivered_explanations
            ]
            
            if ready_explanations:
                logger.debug(f"Found {len(ready_explanations)} ready explanations to deliver")
            
            return ready_explanations
            
        except Exception as e:
            logger.error(f"Error loading explanations queue: {e}")
            return []

    async def _deliver_explanation(self, explanation: Dict):
        """Deliver an explanation to the frontend via WebSocket"""
        try:
            # Create UniversalMessage for the explanation
            message = UniversalMessage(
                id=f"explanation_delivery_{explanation.get('id', 'unknown')}",
                type="explanation.new",
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
                        "confidence": explanation.get("confidence", 1.0)
                    }
                },
                # Route to specific client if available and frontend, otherwise to all frontends
                destination=explanation.get("client_id") if explanation.get("client_id", "").startswith("frontend_") else "all_frontends",
                origin="explanation_delivery_service",
                client_id=explanation.get("client_id"),
            )
            
            # Send to WebSocket queue for delivery
            await self.outgoing_queue.enqueue(message)
            
            logger.info(f"Delivered explanation for term '{explanation.get('term')}' (id: {explanation.get('id')}) to {message.destination}")
            
        except Exception as e:
            logger.error(f"Error delivering explanation {explanation.get('id')}: {e}", exc_info=True)

    async def _mark_as_delivered(self, explanation_id: str):
        """Mark an explanation as delivered in the queue file"""
        try:
            # Read current explanations
            with open(self.explanations_file, 'r', encoding='utf-8') as f:
                explanations = json.load(f)
            
            # Update status to delivered
            for explanation in explanations:
                if explanation.get("id") == explanation_id:
                    explanation["status"] = "delivered"
                    explanation["delivered_at"] = time.time()
                    break
            
            # Write back to file atomically
            temp_file = self.explanations_file.with_suffix('.tmp')
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(explanations, f, indent=2, ensure_ascii=False)
            
            # Atomic rename
            temp_file.replace(self.explanations_file)
            
            logger.debug(f"Marked explanation {explanation_id} as delivered")
            
        except Exception as e:
            logger.error(f"Error marking explanation {explanation_id} as delivered: {e}")

    async def force_deliver_all_ready(self):
        """Force delivery of all ready explanations (useful for testing)"""
        logger.info("Force delivering all ready explanations")
        ready_explanations = await self._load_ready_explanations()
        
        for explanation in ready_explanations:
            explanation_id = explanation.get("id")
            if explanation_id and explanation_id not in self.delivered_explanations:
                await self._deliver_explanation(explanation)
                self.delivered_explanations.add(explanation_id)
                await self._mark_as_delivered(explanation_id)
        
        logger.info(f"Force delivered {len(ready_explanations)} explanations")

    def get_status(self) -> Dict:
        """Get service status for debugging"""
        return {
            "running": self._running,
            "delivered_count": len(self.delivered_explanations),
            "queue_file_exists": self.explanations_file.exists(),
            "delivered_ids": list(self.delivered_explanations)[:10]  # Show last 10 for brevity
        }

    def reset_delivered_tracking(self):
        """Reset delivered explanations tracking (useful for testing)"""
        self.delivered_explanations.clear()
        logger.info("Reset delivered explanations tracking")