import json
import httpx  # Use httpx for asynchronous HTTP requests
import os
import time
import aiofiles
import asyncio
import logging
from pathlib import Path
from typing import Dict, List, Optional
import uuid # FIX: Added missing import for uuid

from ..models.UniversalMessage import UniversalMessage, ErrorTypes

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

        # A single, reusable async HTTP client is more efficient.
        self.http_client = httpx.AsyncClient(timeout=60.0)

        # CRITICAL FIX: Locks to prevent race conditions when accessing shared files.
        # Each file that is read, modified, and then written back needs its own lock.
        self.detections_lock = asyncio.Lock()
        self.explanations_lock = asyncio.Lock()
        self.cache_lock = asyncio.Lock()

        # Cooldown tracking (Note: this is still in-memory and will reset on restart)
        self.explained_terms = {}

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

    def build_prompt(self, term: str, context: str, user_role: Optional[str] = None) -> List[Dict]:
        role_context = ""
        if user_role:
            role_context = f" The user is a '{user_role}', so adjust your explanation accordingly."

        return [
            {
                "role": "system",
                "content": f"You are a helpful assistant explaining technical terms in simple, clear language.{role_context}"
            },
            {
                "role": "user",
                "content": f"""Please directly explain the term "{term}" as used in this context:
"{context}"

Provide a clear, concise explanation in 1-2 sentences. Focus on what the term means and why it's important. Do not include reasoning or thought processes."""
            }
        ]

    async def query_llm(self, messages: List[Dict], model: str = MODEL) -> Optional[str]:
        """
        FIX: Asynchronously query the LLM using httpx to prevent blocking.
        """
        try:
            response = await self.http_client.post(
                OLLAMA_API_URL,
                json={"model": model, "messages": messages, "stream": False},
            )
            response.raise_for_status()
            raw_response = response.json()["message"]["content"].strip()
            return self.clean_output(raw_response)
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error querying LLM: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            logger.error(f"Error querying LLM: {e}", exc_info=True)
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

                # Find pending items and update their status in-place to prevent re-processing
                something_to_process = False
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
            except Exception as e:
                logger.error(f"Error reading detections queue: {e}", exc_info=True)
                return

        if not pending_detections:
            return

        # --- Stage 2: Process the items outside the lock to avoid blocking other writers ---
        cache = await self.load_cache()
        
        for entry in pending_detections:
            term = entry["term"]
            
            if self.is_explained(term):
                logger.debug(f"Term '{term}' recently explained, skipping.")
                continue

            explanation = cache.get(term)
            if not explanation:
                logger.info(f"Generating new explanation for '{term}'...")
                messages = self.build_prompt(term, entry["context"], entry.get("user_role"))
                explanation = await self.query_llm(messages)

                if explanation:
                    cache[term] = explanation
                    await self.save_cache(cache)
                    logger.info(f"Generated and cached explanation for '{term}'.")
                else:
                    logger.warning(f"Failed to generate explanation for '{term}'.")
                    continue # Skip to next term if explanation fails
            else:
                logger.info(f"Loaded explanation for '{term}' from cache.")

            # Create and write the final explanation entry
            explanation_entry = {
                "id": str(uuid.uuid4()), "term": term, "explanation": explanation,
                "context": entry["context"], "timestamp": int(time.time()),
                "client_id": entry.get("client_id"), "user_session_id": entry.get("user_session_id"),
                "original_detection_id": entry.get("id"), "status": "ready_for_delivery"
            }
            
            if await self.write_explanation_to_queue(explanation_entry):
                self.mark_as_explained(term)
                logger.info(f"Successfully processed and queued explanation for term '{term}'.")

    async def run_continuous_processing(self):
        """Run continuous processing loop for detected terms."""
        logger.info(f"Starting MainModel continuous processing, monitoring: {self.detections_queue_file}")
        while True:
            try:
                await self.process_detections_queue()
                await asyncio.sleep(2)
            except asyncio.CancelledError:
                logger.info("MainModel processing task cancelled.")
                break
            except Exception as e:
                logger.error(f"Unexpected error in MainModel run loop: {e}", exc_info=True)
                await asyncio.sleep(30)
    
    async def close(self):
        """Gracefully close the HTTP client."""
        await self.http_client.aclose()
        logger.info("MainModel HTTP client closed.")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    main_model = MainModel()
    
    # Use asyncio.run for cleaner startup and shutdown
    try:
        asyncio.run(main_model.run_continuous_processing())
    except KeyboardInterrupt:
        logger.info("MainModel shutdown initiated by user.")
    finally:
        # Gracefully close resources in a final async operation
        asyncio.run(main_model.close())
        logger.info("MainModel shutdown complete.")