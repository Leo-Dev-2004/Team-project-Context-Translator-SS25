import json
import httpx  # Use httpx for asynchronous HTTP requests
import os
import time
import aiofiles
import asyncio
import logging
from pathlib import Path
from typing import Dict, List, Optional
import uuid

from ..models.UniversalMessage import UniversalMessage, ErrorTypes
from ..dependencies import get_explanation_delivery_service_instance

# === Config ===
# Moved configuration to constants for clarity
INPUT_FILE = "Backend/AI/detections_queue.json"
OUTPUT_FILE = "Backend/AI/explanations_queue.json"
CACHE_FILE = "Backend/AI/explanation_cache.json"
MODEL = "llama3.2"
COOLDOWN_SECONDS = 300
OLLAMA_API_URL = "http://localhost:11434/api/chat"

# Setup logging
logger = logging.getLogger(__name__)

class MainModel:
    """
    AI-powered explanation model that reads detected terms from a file queue,
    generates explanations, and writes them back to an explanation queue for client delivery.
    
    This version is rewritten to be fully asynchronous and thread-safe, preventing
    data loss and application freezes.
    """

    def __init__(self):
        self.detections_queue_file = Path(INPUT_FILE)
        self.explanations_queue_file = Path(OUTPUT_FILE)
        self.cache_file = Path(CACHE_FILE)

        # Flush queues at startup
        self.detections_queue_file.write_text(json.dumps([]), encoding='utf-8')
        self.explanations_queue_file.write_text(json.dumps([]), encoding='utf-8')
        self.cache_file.write_text(json.dumps({}), encoding='utf-8')

        # A single, reusable async HTTP client is more efficient.
        self.http_client = httpx.AsyncClient(timeout=60.0)

        # Import outgoing queue for immediate explanation updates
        from ..core.Queues import queues
        self.outgoing_queue = queues.outgoing

        # CRITICAL FIX: Locks to prevent race conditions when accessing shared files.
        # Each file that is read, modified, and then written back needs its own lock.
        self.detections_lock = asyncio.Lock()
        self.explanations_lock = asyncio.Lock()
        self.cache_lock = asyncio.Lock()

        # Cooldown tracking (Note: this is still in-memory and will reset on restart)
        self.explained_terms = {}

    async def send_explanation_update(self, term: str, explanation: str, entry: Dict):
        """
        Send immediate explanation update to frontend to progressively enhance detected terms.
        This updates terms that were previously sent as detections with their full explanations.
        """
        try:
            # Create explanation update message
            explanation_update = UniversalMessage(
                type="explanation.update",
                payload={
                    "term": term,
                    "explanation": explanation,
                    "context": entry["context"],
                    "confidence": entry.get("confidence", 0.5),
                    "timestamp": int(time.time()),
                    "original_detection_id": entry.get("id"),
                    "status": "explained"
                },
                client_id=entry.get("client_id"),
                origin="MainModel", 
                destination="frontend"
            )

            # Send immediately to frontend
            await self.outgoing_queue.enqueue(explanation_update)
            
            logger.info(f"Sent explanation update for term '{term}' to client {entry.get('client_id')}")
            
        except Exception as e:
            logger.error(f"Error sending explanation update for '{term}': {e}", exc_info=True)

        # Ensure queue directories exist (synchronous operation at init is acceptable)
        self.detections_queue_file.parent.mkdir(parents=True, exist_ok=True)
        self.explanations_queue_file.parent.mkdir(parents=True, exist_ok=True)

        logger.info("MainModel initialized with asynchronous and thread-safe operations.")

    # No changes needed for these helper methods
    def clean_output(self, text: str) -> str:
        return (
            text.replace("<think>", "")
                .replace("</think>", "")
                .replace("### Response:", "")
                .replace("**Explanation:**", "")
                .strip()
        )

    def is_explained(self, term: str) -> bool:
        now = time.time()
        term = term.lower()
        if term in self.explained_terms:
            last_time = self.explained_terms[term]
            if now - last_time < COOLDOWN_SECONDS:
                return True
        return False

    def mark_as_explained(self, term: str):
        self.explained_terms[term.lower()] = time.time()

    def build_prompt(self, term: str, context: str, user_role: Optional[str] = None, 
                     explanation_style: str = "detailed", is_retry: bool = False, domain: Optional[str] = None) -> List[Dict]:
        role_context = ""
        if user_role:
            role_context = f" The user is a '{user_role}', so adjust your explanation accordingly."

        domain_context = ""
        if domain and isinstance(domain, str) and domain.strip():
            domain_context = f" The explanation should be tailored for someone working in the field of '{domain.strip()}'."

        # Style-specific instructions
        style_instructions = {
            "simple": "Provide a brief, easy-to-understand explanation in 1 sentence.",
            "detailed": "Provide a comprehensive explanation in 2-3 sentences with examples if helpful.",
            "technical": "Provide an in-depth technical explanation with precise terminology and context.",
            "beginner": "Provide an explanation suitable for complete beginners, avoiding jargon and using simple analogies."
        }
        
        style_instruction = style_instructions.get(explanation_style, style_instructions["detailed"])
        
        retry_instruction = ""
        if is_retry:
            retry_instruction = " This is a regeneration request - provide an alternative, more extensive explanation than what might have been given before."

        # Style-specific instructions
        style_instructions = {
            "simple": "Provide a brief, easy-to-understand explanation in 1 sentence.",
            "detailed": "Provide a comprehensive explanation in 2-3 sentences with examples if helpful.",
            "technical": "Provide an in-depth technical explanation with precise terminology and context.",
            "beginner": "Provide an explanation suitable for complete beginners, avoiding jargon and using simple analogies."
        }
        
        style_instruction = style_instructions.get(explanation_style, style_instructions["detailed"])
        
        retry_instruction = ""
        if is_retry:
            retry_instruction = " This is a regeneration request - provide an alternative, more extensive explanation than what might have been given before."

        return [
            {
                "role": "system",
                "content": f"You are a helpful assistant explaining technical terms in clear language.{role_context}{domain_context}{retry_instruction}"
            },
            {
                "role": "user",
                "content": f"""Please directly explain the term "{term}" as used in this context:
"{context}"

{f"Domain focus: {domain.strip()}. " if domain and domain.strip() else ""}Provide a clear, concise explanation in 1-2 sentences. Focus on what the term means and why it's important. Do not include reasoning or thought processes."""
            }
        ]

    async def query_llm(self, messages: List[Dict], model: str = MODEL) -> Optional[str]:
        """
        FIX: Asynchronously query the LLM using httpx to prevent blocking.
        """
        import psutil, time
        start_time = time.time()
        try:
            response = await self.http_client.post(
                OLLAMA_API_URL,
                json={"model": model, "messages": messages, "stream": False},
            )
            response.raise_for_status()
            raw_response = response.json()["message"]["content"].strip()
            elapsed = time.time() - start_time
            if elapsed > 10:
                logger.warning(f"LLM response time slow: {elapsed:.2f}s. Possible resource exhaustion.")
            mem = psutil.virtual_memory()
            if mem.percent > 90:
                logger.warning(f"High memory usage detected: {mem.percent}%. Possible resource exhaustion.")
            return self.clean_output(raw_response)
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error querying LLM: {e.response.status_code} - {e.response.text}. Possible Ollama connection issue or model error.")
        except httpx.RequestError as e:
            logger.error(f"Ollama connection failed: {e}. Ollama may not be running or reachable.")
        except Exception as e:
            logger.error(f"Error querying LLM: {e}. Possible backend shutdown or unexpected error.", exc_info=True)
        return None

    async def load_cache(self) -> Dict[str, str]:
        """Load explanation cache from file safely."""
        async with self.cache_lock:
            try:
                # Use try/except instead of a blocking .exists() call
                async with aiofiles.open(self.cache_file, 'r', encoding='utf-8') as f:
                    content = await f.read()
                    return json.loads(content) if content.strip() else {}
            except FileNotFoundError:
                return {} # Return empty cache if file doesn't exist
            except Exception as e:
                logger.error(f"Error loading cache: {e}")
                return {}

    async def save_cache(self, cache: Dict[str, str]):
        """Save explanation cache to file atomically and safely."""
        async with self.cache_lock:
            try:
                temp_file = self.cache_file.with_suffix('.tmp')
                async with aiofiles.open(temp_file, 'w', encoding='utf-8') as f:
                    await f.write(json.dumps(cache, indent=2, ensure_ascii=False))
                
                # FIX: Run the blocking os.replace call in a separate thread
                await asyncio.to_thread(os.replace, str(temp_file), str(self.cache_file))
            except Exception as e:
                logger.error(f"Error saving cache: {e}")

    async def write_explanation_to_queue(self, explanation_entry: Dict) -> bool:
        """
        FIX: Write explanation to output queue safely using a lock to prevent race conditions.
        """
        async with self.explanations_lock:
            try:
                current_queue = []
                try:
                    async with aiofiles.open(self.explanations_queue_file, 'r', encoding='utf-8') as f:
                        content = await f.read()
                        if content.strip():
                            current_queue = json.loads(content)
                except FileNotFoundError:
                    logger.info("Explanations queue file not found, creating a new one.")

                current_queue.append(explanation_entry)

                temp_file = self.explanations_queue_file.with_suffix('.tmp')
                async with aiofiles.open(temp_file, 'w', encoding='utf-8') as f:
                    await f.write(json.dumps(current_queue, indent=2, ensure_ascii=False))
                
                await asyncio.to_thread(os.replace, str(temp_file), str(self.explanations_queue_file))
                
                logger.info(f"Successfully wrote explanation to queue for client {explanation_entry.get('client_id')}")
                
                # Trigger immediate check in ExplanationDeliveryService for faster delivery
                delivery_service = get_explanation_delivery_service_instance()
                if delivery_service:
                    delivery_service.trigger_immediate_check()
                    logger.debug("Triggered immediate explanation delivery check")
                
                return True
            except Exception as e:
                logger.error(f"Error writing explanation to queue: {e}", exc_info=True)
                return False

    async def process_detections_queue(self):
        """Process detected terms from SmallModel and generate explanations."""
        pending_detections = []
        
        # --- Stage 1: Safely read and update the detections queue ---
        async with self.detections_lock:
            all_detections = []
            try:
                async with aiofiles.open(self.detections_queue_file, 'r', encoding='utf-8') as f:
                    content = await f.read()
                all_detections = json.loads(content) if content.strip() else []
                if not all_detections:
                    return

                something_to_process = False
                pending_detections = []
                for entry in all_detections:
                    if entry.get("status") == "pending":
                        pending_detections.append(entry)
                        entry["status"] = "processing"
                        something_to_process = True

                if something_to_process:
                    temp_file = self.detections_queue_file.with_suffix('.tmp')
                    async with aiofiles.open(temp_file, 'w', encoding='utf-8') as f:
                        await f.write(json.dumps(all_detections, indent=2, ensure_ascii=False))
                    await asyncio.to_thread(os.replace, str(temp_file), str(self.detections_queue_file))
                    logger.info(f"Marked {len(pending_detections)} detections as 'processing'.")
            except FileNotFoundError:
                return
        # --- Stage 2: Process the items outside the lock to avoid blocking other writers ---
        if not pending_detections:
            return

        cache = await self.load_cache()
        for entry in pending_detections:
            term = entry["term"]
            is_retry = entry.get("is_retry", False)
            explanation_style = entry.get("explanation_style", "detailed")
            original_explanation_id = entry.get("original_explanation_id")
            
            # For retry requests, skip cache and cooldown checks
            if not is_retry and self.is_explained(term):
                logger.debug(f"Term '{term}' recently explained, skipping.")
                continue

            explanation = cache.get(term)
            if not explanation:
                logger.info(f"Generating new explanation for '{term}'...")
                messages = self.build_prompt(term, entry["context"], entry.get("user_role"), entry.get("domain"))
                explanation = await self.query_llm(messages)
                if explanation:
                    cache[term] = explanation
                    await self.save_cache(cache)
                    logger.info(f"Generated and cached explanation for '{term}'.")
                else:
                    logger.info(f"Loaded explanation for '{term}' from cache.")


            if not explanation:
                logger.warning(f"Failed to generate explanation for '{term}'.")
                continue

            # IMMEDIATE FEEDBACK: Send explanation update to frontend right away
            await self.send_explanation_update(term, explanation, entry)

            message_type = "explanation.retry" if is_retry else "explanation.new"
            explanation_entry = {
                "id": str(uuid.uuid4()), "term": term, "explanation": explanation,
                "context": entry["context"], "timestamp": int(time.time()),
                "client_id": entry.get("client_id"), "user_session_id": entry.get("user_session_id"),
                "original_detection_id": entry.get("id"), "status": "ready_for_delivery",
                "confidence": entry.get("confidence", 0), "message_type": message_type
            }
            if is_retry and original_explanation_id:
                explanation_entry["original_explanation_id"] = original_explanation_id

            # Add original explanation ID for retry responses
            if is_retry and original_explanation_id:
                explanation_entry["original_explanation_id"] = original_explanation_id
            
            # BACKGROUND: Still queue for file-based delivery system (backwards compatibility)
            if await self.write_explanation_to_queue(explanation_entry):
                # Only mark as explained for non-retry requests
                if not is_retry:
                    self.mark_as_explained(term)
                logger.info(f"Successfully processed and queued {'retry ' if is_retry else ''}explanation for term '{term}'.")

    async def run_continuous_processing(self):
        """Run continuous processing loop for detected terms."""
        logger.info(f"Starting MainModel continuous processing, monitoring: {self.detections_queue_file}")
        while True:
            try:
                await self.process_detections_queue()
                await asyncio.sleep(1)
            except asyncio.CancelledError:
                logger.info("MainModel processing cancelled by shutdown")
                break
            except KeyboardInterrupt:
                logger.info("MainModel processing stopped by user")
                break