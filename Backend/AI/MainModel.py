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
from ..dependencies import get_settings_manager_instance
from ..dependencies import get_explanation_delivery_service_instance
# REMOVED: from .ollama_client import ollama_client

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
        self.detections_lock = asyncio.Lock()
        self.explanations_lock = asyncio.Lock()
        self.cache_lock = asyncio.Lock()

        # Cooldown tracking
        self.explained_terms = {}

    async def send_explanation_update(self, term: str, explanation: str, entry: Dict):
        """
        Sends an immediate explanation update to the frontend.
        """
        try:
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
            await self.outgoing_queue.enqueue(explanation_update)
            logger.info(f"Sent explanation update for term '{term}' to client {entry.get('client_id')}")
        except Exception as e:
            logger.error(f"Error sending explanation update for '{term}': {e}", exc_info=True)

        self.detections_queue_file.parent.mkdir(parents=True, exist_ok=True)
        self.explanations_queue_file.parent.mkdir(parents=True, exist_ok=True)
        logger.info("MainModel initialized with asynchronous and thread-safe operations.")

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
        """Builds the prompt for the LLM explanation generation."""
        settings_manager = get_settings_manager_instance()
        if settings_manager:
            if not domain:
                domain = settings_manager.get_setting("domain", "")
            if explanation_style == "detailed":
                explanation_style = settings_manager.get_setting("explanation_style", "detailed")
        
        role_context = f" The user is a '{user_role}', so adjust your explanation accordingly." if user_role else ""
        domain_context = f" The explanation should be tailored for someone in the '{domain.strip()}' field." if domain and domain.strip() else ""
        retry_instruction = " This is a regeneration request - provide an alternative, more extensive explanation." if is_retry else ""

        style_instructions = {
            "simple": "Provide a brief, easy-to-understand explanation in 1 sentence.",
            "detailed": "Provide a comprehensive explanation in 2-3 sentences with examples if helpful.",
            "technical": "Provide an in-depth technical explanation with precise terminology.",
            "beginner": "Provide an explanation for complete beginners, using simple analogies."
        }
        style_instruction = style_instructions.get(explanation_style, style_instructions["detailed"])

        return [
            {
                "role": "system",
                "content": f"You are a helpful assistant explaining technical terms in clear language.{role_context}{domain_context}{retry_instruction}"
            },
            {
                "role": "user",
                "content": f"""Please directly explain the term "{term}" as used in this context:
"{context}"

{f"Domain focus: {domain.strip()}. " if domain and domain.strip() else ""}{style_instruction} Focus on what the term means and why it's important. Do not include your reasoning."""
            }
        ]

    def _extract_text_from_response(self, data: Dict) -> Optional[str]:
        """Extracts the assistant's text content from an Ollama JSON response."""
        try:
            if not isinstance(data, dict):
                return None
            
            # For /api/chat (non-streaming)
            if 'message' in data and isinstance(data['message'], dict) and 'content' in data['message']:
                return data['message']['content']
            
            # For /api/generate (non-streaming)
            if 'response' in data and isinstance(data['response'], str):
                return data['response']

            return None
        except Exception:
            logger.debug("Failed to extract assistant text from response", exc_info=True)
            return None

    async def query_llm(self, messages: List[Dict], model: str = MODEL) -> Optional[str]:
        """Asynchronously queries the Ollama server and returns the text content."""
        payload = {
            "model": model,
            "messages": messages,
            "stream": False
        }
        
        try:
            response = await self.http_client.post(OLLAMA_API_URL, json=payload)
            response.raise_for_status()
            
            json_response = response.json()
            text_content = self._extract_text_from_response(json_response)
            
            if text_content is None:
                logger.error("Could not extract text from Ollama response: %s", json_response)
                return None
            
            return self.clean_output(text_content)

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error querying LLM: {e.response.status_code} - {e.response.text}")
        except httpx.RequestError as e:
            logger.error(f"Ollama connection failed: {e}. Is Ollama running?")
        except json.JSONDecodeError:
            logger.error(f"Failed to decode JSON from Ollama response: {response.text}")
        except Exception as e:
            logger.error(f"Error querying LLM: {e}", exc_info=True)
        return None

    async def load_cache(self) -> Dict[str, str]:
        """Loads the explanation cache from a file."""
        async with self.cache_lock:
            try:
                async with aiofiles.open(self.cache_file, 'r', encoding='utf-8') as f:
                    content = await f.read()
                    return json.loads(content) if content.strip() else {}
            except FileNotFoundError:
                return {}
            except Exception as e:
                logger.error(f"Error loading cache: {e}")
                return {}

    async def save_cache(self, cache: Dict[str, str]):
        """Saves the explanation cache to a file atomically."""
        async with self.cache_lock:
            try:
                temp_file = self.cache_file.with_suffix('.tmp')
                async with aiofiles.open(temp_file, 'w', encoding='utf-8') as f:
                    await f.write(json.dumps(cache, indent=2, ensure_ascii=False))
                await asyncio.to_thread(os.replace, str(temp_file), str(self.cache_file))
            except Exception as e:
                logger.error(f"Error saving cache: {e}")

    async def write_explanation_to_queue(self, explanation_entry: Dict) -> bool:
        """Writes an explanation entry to the output queue file."""
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
                
                delivery_service = get_explanation_delivery_service_instance()
                if delivery_service:
                    delivery_service.trigger_immediate_check()
                    logger.debug("Triggered immediate explanation delivery check")
                
                return True
            except Exception as e:
                logger.error(f"Error writing explanation to queue: {e}", exc_info=True)
                return False

    async def process_detections_queue(self):
        """Processes detected terms from SmallModel and generates explanations."""
        pending_detections = []
        
        async with self.detections_lock:
            all_detections = []
            try:
                async with aiofiles.open(self.detections_queue_file, 'r', encoding='utf-8') as f:
                    content = await f.read()
                all_detections = json.loads(content) if content.strip() else []
                if not all_detections:
                    return

                items_to_keep = [e for e in all_detections if e.get("status") != "pending"]
                pending_detections = [e for e in all_detections if e.get("status") == "pending"]

                if pending_detections:
                    temp_file = self.detections_queue_file.with_suffix('.tmp')
                    async with aiofiles.open(temp_file, 'w', encoding='utf-8') as f:
                        await f.write(json.dumps(items_to_keep, indent=2, ensure_ascii=False))
                    await asyncio.to_thread(os.replace, str(temp_file), str(self.detections_queue_file))
                    logger.info(f"Atomically moved {len(pending_detections)} detections from queue for processing.")
            except FileNotFoundError:
                return

        if not pending_detections:
            return

        cache = await self.load_cache()
        for entry in pending_detections:
            term = entry["term"]
            is_retry = entry.get("is_retry", False)
            is_manual_request = entry.get("is_manual_request", False)
            
            if not is_retry and self.is_explained(term):
                logger.debug(f"Term '{term}' recently explained, skipping.")
                continue

            explanation = cache.get(term)
            if not explanation or is_retry:
                logger.info(f"Generating {'new' if not is_retry else 'retry'} explanation for '{term}'...")
                messages = self.build_prompt(term, entry["context"], entry.get("user_role"), entry.get("explanation_style"), is_retry, entry.get("domain"))
                explanation = await self.query_llm(messages)
                if explanation:
                    cache[term] = explanation
                    await self.save_cache(cache)
            else:
                logger.info(f"Loaded explanation for '{term}' from cache.")

            if not explanation:
                logger.warning(f"Failed to generate explanation for '{term}'.")
                continue

            # Send the update directly to the frontend.
            await self.send_explanation_update(term, explanation, entry)

            # Mark the term as explained to respect the cooldown.
            if not is_retry:
                self.mark_as_explained(term)

    async def run_continuous_processing(self):
        """Runs the continuous processing loop for detected terms."""
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