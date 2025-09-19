import logging
import json
import asyncio
import os
import httpx
from ..shared.communications.ConnectionManager import ConnectionManager
from ..models.UniversalMessage import UniversalMessage

logger = logging.getLogger(__name__)

# === Config ===
CACHE_FILE = "explanation_cache.json"
MODEL = "qwen3"
OLLAMA_API_URL = "http://localhost:11434/api/chat"

class MainModel:
    """
    Runs as a background service to generate explanations for terms received from a queue.
    """
    def __init__(self, queue: asyncio.Queue, connection_manager: ConnectionManager):
        self.queue = queue
        self.connection_manager = connection_manager
        self.model = MODEL
        self.cache_file = CACHE_FILE
        self.explanation_cache = self._load_cache() 
        logger.info("MainModel initialized with in-memory explanation cache.")

    # FIX: This method needs `self` to access `self.cache_file`
    def _load_cache(self) -> dict:
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r", encoding='utf-8') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                logger.error(f"Could not decode JSON from cache file: {self.cache_file}")
                return {}
        return {}

    # FIX: This method needs `self` to access the instance's cache and file path
    def _save_cache(self):
        try:
            with open(self.cache_file, "w", encoding='utf-8') as f:
                json.dump(self.explanation_cache, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save explanation cache: {e}")

    # FIX: These helpers don't need `self`, so they are marked as @staticmethod
    @staticmethod
    def _clean_output(text: str) -> str:
        """Cleans the raw text from the LLM."""
        return text.replace("### Response:", "").replace("**Explanation:**", "").strip()

    @staticmethod
    def _build_prompt(term: str, context: str) -> list:
        """Builds the request for the LLM."""
        return [
            {"role": "system", "content": "You are a helpful assistant explaining terms in simple, clear language."},
            {"role": "user", "content": f'Please directly explain the term "{term}" in the context of the sentence: "{context}". Your answer must be a short, clear definition only in 1-2 sentences.'}
        ]

    @staticmethod
    async def _query_llm(messages: list, model=MODEL) -> str | None:
        """Asynchronously queries the LLM using httpx."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    OLLAMA_API_URL,
                    json={"model": model, "messages": messages, "stream": False}
                )
                response.raise_for_status()
                raw_response = response.json()["message"]["content"].strip()
                # FIX: Call the static method correctly
                return MainModel._clean_output(raw_response)
        except httpx.RequestError as e:
            logger.error(f"LLM query failed (HTTP request error): {e}")
            return None
        except Exception as e:
            logger.error(f"LLM query failed (general error): {e}")
            return None

    # FIX: The main run loop MUST have `self` to access the queue, manager, cache, etc.
    async def run(self):
        """The main loop to consume tasks from the queue and process them."""
        logger.info("MainModel background task started. Waiting for explanation tasks...")
        while True:
            try:
                task = await self.queue.get()
                
                term = task.get("term")
                context = task.get("context")
                client_id = task.get("client_id")

                if not all([term, context, client_id]):
                    logger.warning(f"Invalid task received, missing keys: {task}")
                    self.queue.task_done()
                    continue
                
                logger.info(f"Dequeued task: Explain '{term}' for client {client_id}")

                if term in self.explanation_cache:
                    explanation = self.explanation_cache[term]
                    logger.info(f"Found explanation for '{term}' in cache.")
                else:
                    logger.info(f"Querying LLM for new explanation of '{term}'...")
                    # FIX: Call static methods using self or the Class name
                    messages = self._build_prompt(term, context)
                    explanation = await self._query_llm(messages, self.model)

                    if explanation:
                        self.explanation_cache[term] = explanation
                        self._save_cache() # FIX: Call with self
                    else:
                        explanation = f"Sorry, I could not generate an explanation for '{term}'."

                response_message = UniversalMessage(
                    type="ai.explanation",
                    payload={"term": term, "explanation": explanation},
                    origin="main_model",
                    destination=client_id,
                    client_id=client_id
                )
                
                try:
                    await self.connection_manager.send_to_client(
                        client_id,
                        response_message.model_dump_json()
                    )
                except Exception as send_error:
                    logger.warning(f"Failed to send explanation to client {client_id} (they may have disconnected): {send_error}")

            except asyncio.CancelledError:
                logger.info("MainModel task is shutting down.")
                break
            except Exception as e:
                logger.error(f"Critical error in MainModel run loop: {e}", exc_info=True)
                await asyncio.sleep(5)
            finally:
                if 'task' in locals() and not self.queue.empty():
                    self.queue.task_done()